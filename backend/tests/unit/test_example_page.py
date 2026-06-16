from pathlib import Path

from app.main import _resolve_frontend_static_dir, validate_credentials


def test_resolve_frontend_static_dir_requires_index_file(tmp_path: Path) -> None:
    static_dir = tmp_path / "frontend-out"
    static_dir.mkdir()
    assert _resolve_frontend_static_dir(static_dir) is None


def test_resolve_frontend_static_dir_returns_resolved_path(tmp_path: Path) -> None:
    static_dir = tmp_path / "frontend-out"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<h1>Kanban Studio</h1>", encoding="utf-8")
    assert _resolve_frontend_static_dir(static_dir) == static_dir.resolve()


def test_validate_credentials_accepts_expected_values() -> None:
    assert validate_credentials("user", "password")


def test_validate_credentials_rejects_unexpected_values() -> None:
    assert not validate_credentials("user", "wrong")
    assert not validate_credentials("someone", "password")
