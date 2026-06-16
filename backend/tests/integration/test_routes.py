from fastapi.testclient import TestClient

from app.main import create_app


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
    assert response.json() == {"authenticated": False}


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
    assert login_response.json() == {"authenticated": True}
    assert "pm_session=authenticated" in login_response.headers["set-cookie"]

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json() == {"authenticated": True}


def test_logout_clears_cookie() -> None:
    client = TestClient(create_app())
    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json() == {"authenticated": False}

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json() == {"authenticated": False}


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
