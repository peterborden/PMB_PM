import copy

from fastapi.testclient import TestClient

from app.main import create_app


class FakeAIClient:
    def run_diagnostic(self):
        return {"model": "openai/gpt-oss-120b", "prompt": "2+2", "answer": "4"}

    def run_board_assistant(self, board, history, user_message):
        updated = copy.deepcopy(board)
        updated["columns"][0]["title"] = f"AI: {user_message}"
        return {"reply": f"Handled: {user_message}", "updatedBoard": updated}


def _client(tmp_path, ai_client=None):
    return TestClient(
        create_app(db_path=tmp_path / "test.db", ai_client=ai_client or FakeAIClient())
    )


def _register(client, username="alice", password="password123"):
    return client.post(
        "/api/auth/register", json={"username": username, "password": password}
    )


# ---------------------------------------------------------------------------
# Registration & login
# ---------------------------------------------------------------------------


def test_register_creates_user_and_logs_in(tmp_path) -> None:
    client = _client(tmp_path)
    response = _register(client)
    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "username": "alice"}

    session = client.get("/api/auth/session")
    assert session.json() == {"authenticated": True, "username": "alice"}


def test_register_rejects_duplicate_username(tmp_path) -> None:
    client = _client(tmp_path)
    _register(client)
    duplicate = _register(TestClient(create_app(db_path=tmp_path / "test.db")), "alice")
    assert duplicate.status_code == 409


def test_register_validates_username_and_password(tmp_path) -> None:
    client = _client(tmp_path)
    assert client.post(
        "/api/auth/register", json={"username": "ab", "password": "password123"}
    ).status_code == 422
    assert client.post(
        "/api/auth/register", json={"username": "valid", "password": "short"}
    ).status_code == 422
    assert client.post(
        "/api/auth/register", json={"username": "has space", "password": "password123"}
    ).status_code == 422


def test_login_with_registered_credentials(tmp_path) -> None:
    _register(_client(tmp_path))
    fresh = TestClient(create_app(db_path=tmp_path / "test.db"))
    login = fresh.post(
        "/api/auth/login", json={"username": "alice", "password": "password123"}
    )
    assert login.status_code == 200
    assert login.json() == {"authenticated": True, "username": "alice"}


def test_logout_invalidates_session(tmp_path) -> None:
    client = _client(tmp_path)
    _register(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/session").json()["authenticated"] is False
    # The board endpoint should now require auth again.
    assert client.get("/api/boards").status_code == 401


# ---------------------------------------------------------------------------
# Board CRUD
# ---------------------------------------------------------------------------


def test_new_user_has_one_default_board(tmp_path) -> None:
    client = _client(tmp_path)
    _register(client)
    boards = client.get("/api/boards").json()["boards"]
    assert len(boards) == 1
    assert boards[0]["name"] == "My Board"


def test_create_list_and_fetch_boards(tmp_path) -> None:
    client = _client(tmp_path)
    _register(client)
    created = client.post("/api/boards", json={"name": "Roadmap"})
    assert created.status_code == 201
    board_id = created.json()["id"]

    boards = client.get("/api/boards").json()["boards"]
    assert [b["name"] for b in boards] == ["My Board", "Roadmap"]

    detail = client.get(f"/api/boards/{board_id}").json()
    assert detail["name"] == "Roadmap"
    assert detail["version"] == 1
    assert detail["board"]["cards"] == {}


def test_save_board_increments_version(tmp_path) -> None:
    client = _client(tmp_path)
    _register(client)
    board_id = client.get("/api/boards").json()["boards"][0]["id"]
    detail = client.get(f"/api/boards/{board_id}").json()

    updated = copy.deepcopy(detail["board"])
    updated["columns"][0]["title"] = "Renamed Column"
    save = client.put(
        f"/api/boards/{board_id}",
        json={"board": updated, "expectedVersion": detail["version"]},
    )
    assert save.status_code == 200
    assert save.json()["version"] == 2
    assert save.json()["board"]["columns"][0]["title"] == "Renamed Column"


def test_save_board_rejects_version_conflict(tmp_path) -> None:
    client = _client(tmp_path)
    _register(client)
    board_id = client.get("/api/boards").json()["boards"][0]["id"]
    detail = client.get(f"/api/boards/{board_id}").json()
    conflict = client.put(
        f"/api/boards/{board_id}",
        json={"board": detail["board"], "expectedVersion": 999},
    )
    assert conflict.status_code == 409


def test_rename_board(tmp_path) -> None:
    client = _client(tmp_path)
    _register(client)
    board_id = client.get("/api/boards").json()["boards"][0]["id"]
    renamed = client.patch(f"/api/boards/{board_id}", json={"name": "Q3 Plan"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Q3 Plan"


def test_delete_board_and_last_board_protection(tmp_path) -> None:
    client = _client(tmp_path)
    _register(client)
    extra = client.post("/api/boards", json={"name": "Scratch"}).json()
    assert client.delete(f"/api/boards/{extra['id']}").status_code == 204

    remaining = client.get("/api/boards").json()["boards"]
    assert len(remaining) == 1
    # Deleting the last board is refused.
    assert client.delete(f"/api/boards/{remaining[0]['id']}").status_code == 409


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


def test_users_cannot_access_each_others_boards(tmp_path) -> None:
    alice = _client(tmp_path)
    _register(alice, "alice")
    alice_board = alice.get("/api/boards").json()["boards"][0]["id"]

    bob = TestClient(create_app(db_path=tmp_path / "test.db"))
    _register(bob, "bob")

    assert bob.get(f"/api/boards/{alice_board}").status_code == 404
    assert bob.delete(f"/api/boards/{alice_board}").status_code == 404
    assert bob.patch(f"/api/boards/{alice_board}", json={"name": "hijack"}).status_code == 404


# ---------------------------------------------------------------------------
# Per-board AI chat
# ---------------------------------------------------------------------------


def test_board_ai_chat_updates_targeted_board(tmp_path) -> None:
    client = _client(tmp_path)
    _register(client)
    board_id = client.get("/api/boards").json()["boards"][0]["id"]

    response = client.post(
        f"/api/boards/{board_id}/ai/chat", json={"message": "tidy up"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["boardUpdated"] is True
    assert payload["board"]["columns"][0]["title"] == "AI: tidy up"

    persisted = client.get(f"/api/boards/{board_id}").json()
    assert persisted["board"]["columns"][0]["title"] == "AI: tidy up"


def test_board_ai_chat_requires_auth(tmp_path) -> None:
    client = _client(tmp_path)
    _register(client)
    board_id = client.get("/api/boards").json()["boards"][0]["id"]
    client.post("/api/auth/logout")
    assert client.post(
        f"/api/boards/{board_id}/ai/chat", json={"message": "hi"}
    ).status_code == 401


def test_board_ai_chat_rejects_foreign_board(tmp_path) -> None:
    alice = _client(tmp_path)
    _register(alice, "alice")
    alice_board = alice.get("/api/boards").json()["boards"][0]["id"]

    bob = _client(tmp_path)
    _register(bob, "bob")
    assert bob.post(
        f"/api/boards/{alice_board}/ai/chat", json={"message": "hi"}
    ).status_code == 404
