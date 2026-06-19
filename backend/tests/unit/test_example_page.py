from pathlib import Path

from app.main import _resolve_frontend_static_dir
from app.repository import MVP_PASSWORD, MVP_USERNAME, authenticate_user


def test_resolve_frontend_static_dir_requires_index_file(tmp_path: Path) -> None:
    static_dir = tmp_path / "frontend-out"
    static_dir.mkdir()
    assert _resolve_frontend_static_dir(static_dir) is None


def test_resolve_frontend_static_dir_returns_resolved_path(tmp_path: Path) -> None:
    static_dir = tmp_path / "frontend-out"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<h1>Kanban Studio</h1>", encoding="utf-8")
    assert _resolve_frontend_static_dir(static_dir) == static_dir.resolve()


def test_authenticate_seeded_user_accepts_expected_values(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    user = authenticate_user(MVP_USERNAME, MVP_PASSWORD, db_path=db_path)
    assert user is not None
    assert user["username"] == MVP_USERNAME


def test_authenticate_seeded_user_rejects_unexpected_values(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    assert authenticate_user(MVP_USERNAME, "wrong", db_path=db_path) is None
    assert authenticate_user("someone", MVP_PASSWORD, db_path=db_path) is None
