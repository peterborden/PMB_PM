import copy

from fastapi.testclient import TestClient

from app.ai import AIRequestError
from app.main import create_app
from app.repository import DEFAULT_BOARD


def _build_frontend_fixture(tmp_path):
    static_dir = tmp_path / "frontend-out"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        "<!doctype html><html><body><h1>Kanban Studio</h1></body></html>",
        encoding="utf-8",
    )
    nested_dir = static_dir / "docs"
    nested_dir.mkdir()
    (nested_dir / "index.html").write_text(
        "<!doctype html><html><body><h2>Docs page</h2></body></html>",
        encoding="utf-8",
    )
    assets_dir = static_dir / "_next" / "static"
    assets_dir.mkdir(parents=True)
    (assets_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")
    return static_dir


class FakeAIClient:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result or {"model": "openai/gpt-oss-120b", "prompt": "2+2", "answer": "4"}
        self.error = error

    def run_diagnostic(self):
        if self.error is not None:
            raise self.error
        return self.result

    def run_board_assistant(self, board, history, user_message):
        if self.error is not None:
            raise self.error
        return {
            "reply": f"Handled: {user_message}",
            "updatedBoard": None,
        }


def test_root_serves_frontend_index(tmp_path) -> None:
    client = TestClient(create_app(_build_frontend_fixture(tmp_path)))
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Kanban Studio" in response.text


def test_static_asset_path_is_served(tmp_path) -> None:
    client = TestClient(create_app(_build_frontend_fixture(tmp_path)))
    response = client.get("/_next/static/app.js")
    assert response.status_code == 200
    assert "console.log('ok');" in response.text


def test_directory_path_serves_nested_index(tmp_path) -> None:
    client = TestClient(create_app(_build_frontend_fixture(tmp_path)))
    response = client.get("/docs")
    assert response.status_code == 200
    assert "Docs page" in response.text


def test_missing_route_falls_back_to_frontend_index(tmp_path) -> None:
    client = TestClient(create_app(_build_frontend_fixture(tmp_path)))
    response = client.get("/kanban")
    assert response.status_code == 200
    assert "Kanban Studio" in response.text


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_session_endpoint_is_false_without_cookie() -> None:
    client = TestClient(create_app())
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "username": None}


def test_login_rejects_invalid_credentials() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_sets_cookie_and_session_is_true() -> None:
    client = TestClient(create_app())
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 200
    assert login_response.json() == {"authenticated": True, "username": "user"}
    assert "pm_session=" in login_response.headers["set-cookie"]

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json() == {"authenticated": True, "username": "user"}


def test_logout_clears_cookie() -> None:
    client = TestClient(create_app())
    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json() == {"authenticated": False, "username": None}

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json() == {"authenticated": False, "username": None}


def test_hello_requires_authentication() -> None:
    client = TestClient(create_app())
    response = client.get("/api/hello")
    assert response.status_code == 401


def test_hello_returns_message_after_login() -> None:
    client = TestClient(create_app())
    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "hello world"}


def test_board_endpoint_requires_authentication() -> None:
    client = TestClient(create_app())
    response = client.get("/api/board")
    assert response.status_code == 401


def test_board_endpoint_returns_seeded_board(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    client = TestClient(create_app(db_path=db_path))
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    response = client.get("/api/board")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == 1
    assert payload["board"]["columns"][0]["title"] == "Backlog"
    assert db_path.exists()


def test_update_board_persists_changes_and_increments_version(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    client = TestClient(create_app(db_path=db_path))
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    initial_response = client.get("/api/board")
    initial_payload = initial_response.json()
    updated_board = copy.deepcopy(initial_payload["board"])
    updated_board["columns"][0]["title"] = "New Backlog"

    update_response = client.put(
        "/api/board",
        json={"board": updated_board, "expectedVersion": initial_payload["version"]},
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["version"] == 2
    assert update_payload["board"]["columns"][0]["title"] == "New Backlog"

    read_response = client.get("/api/board")
    read_payload = read_response.json()
    assert read_payload["version"] == 2
    assert read_payload["board"]["columns"][0]["title"] == "New Backlog"


def test_update_board_rejects_version_conflicts(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    client = TestClient(create_app(db_path=db_path))
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    response = client.put(
        "/api/board",
        json={"board": DEFAULT_BOARD, "expectedVersion": 999},
    )
    assert response.status_code == 409


def test_board_persists_across_app_instances(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    client_a = TestClient(create_app(db_path=db_path))
    client_a.post("/api/auth/login", json={"username": "user", "password": "password"})

    initial_payload = client_a.get("/api/board").json()
    updated_board = copy.deepcopy(initial_payload["board"])
    updated_board["columns"][1]["title"] = "Persisted Discovery"
    client_a.put(
        "/api/board",
        json={"board": updated_board, "expectedVersion": initial_payload["version"]},
    )

    client_b = TestClient(create_app(db_path=db_path))
    client_b.post("/api/auth/login", json={"username": "user", "password": "password"})
    persisted_payload = client_b.get("/api/board").json()
    assert persisted_payload["board"]["columns"][1]["title"] == "Persisted Discovery"


def test_ai_diagnostic_requires_authentication() -> None:
    client = TestClient(create_app(ai_client=FakeAIClient()))
    response = client.get("/api/ai/diagnostic")
    assert response.status_code == 401


def test_ai_diagnostic_returns_result_when_authenticated() -> None:
    client = TestClient(create_app(ai_client=FakeAIClient()))
    client.post("/api/auth/login", json={"username": "user", "password": "password"})
    response = client.get("/api/ai/diagnostic")
    assert response.status_code == 200
    assert response.json() == {
        "model": "openai/gpt-oss-120b",
        "prompt": "2+2",
        "answer": "4",
    }


def test_ai_diagnostic_surfaces_request_errors() -> None:
    client = TestClient(
        create_app(ai_client=FakeAIClient(error=AIRequestError("upstream failed")))
    )
    client.post("/api/auth/login", json={"username": "user", "password": "password"})
    response = client.get("/api/ai/diagnostic")
    assert response.status_code == 502
    assert response.json()["detail"] == "upstream failed"


def test_ai_diagnostic_returns_503_when_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = TestClient(create_app(ai_client=None))
    client.post("/api/auth/login", json={"username": "user", "password": "password"})
    response = client.get("/api/ai/diagnostic")
    assert response.status_code == 503


def test_ai_chat_requires_authentication(tmp_path) -> None:
    client = TestClient(create_app(ai_client=FakeAIClient(), db_path=tmp_path / "test.db"))
    response = client.post("/api/ai/chat", json={"message": "hello"})
    assert response.status_code == 401


def test_ai_chat_returns_reply_without_board_update(tmp_path) -> None:
    client = TestClient(create_app(ai_client=FakeAIClient(), db_path=tmp_path / "test.db"))
    client.post("/api/auth/login", json={"username": "user", "password": "password"})
    board_before = client.get("/api/board").json()

    response = client.post(
        "/api/ai/chat",
        json={
            "message": "what should I do?",
            "history": [{"role": "user", "content": "previous question"}],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["boardUpdated"] is False
    assert payload["version"] == board_before["version"]
    assert payload["reply"] == "Handled: what should I do?"


def test_ai_chat_can_apply_board_update(tmp_path) -> None:
    class UpdatingAIClient(FakeAIClient):
        def run_board_assistant(self, board, history, user_message):
            updated = copy.deepcopy(board)
            updated["columns"][0]["title"] = "AI Backlog"
            return {
                "reply": "Updated board",
                "updatedBoard": updated,
            }

    client = TestClient(create_app(ai_client=UpdatingAIClient(), db_path=tmp_path / "test.db"))
    client.post("/api/auth/login", json={"username": "user", "password": "password"})
    response = client.post("/api/ai/chat", json={"message": "rename backlog"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["boardUpdated"] is True
    assert payload["board"]["columns"][0]["title"] == "AI Backlog"
    assert payload["version"] == 2

    persisted = client.get("/api/board").json()
    assert persisted["board"]["columns"][0]["title"] == "AI Backlog"


def test_ai_chat_surfaces_upstream_errors(tmp_path) -> None:
    client = TestClient(
        create_app(
            ai_client=FakeAIClient(error=AIRequestError("ai failed")),
            db_path=tmp_path / "test.db",
        )
    )
    client.post("/api/auth/login", json={"username": "user", "password": "password"})
    response = client.post("/api/ai/chat", json={"message": "hello"})
    assert response.status_code == 502
    assert response.json()["detail"] == "ai failed"
