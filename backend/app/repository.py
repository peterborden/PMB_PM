import json
import os
import sqlite3
from pathlib import Path

MVP_USERNAME = "user"
MVP_PASSWORD_HASH = "mvp-placeholder-hash"

DEFAULT_BOARD = {
    "columns": [
        {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-2"]},
        {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
        {
            "id": "col-progress",
            "title": "In Progress",
            "cardIds": ["card-4", "card-5"],
        },
        {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
        {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
    ],
    "cards": {
        "card-1": {
            "id": "card-1",
            "title": "Align roadmap themes",
            "details": "Draft quarterly themes with impact statements and metrics.",
        },
        "card-2": {
            "id": "card-2",
            "title": "Gather customer signals",
            "details": "Review support tags, sales notes, and churn feedback.",
        },
        "card-3": {
            "id": "card-3",
            "title": "Prototype analytics view",
            "details": "Sketch initial dashboard layout and key drill-downs.",
        },
        "card-4": {
            "id": "card-4",
            "title": "Refine status language",
            "details": "Standardize column labels and tone across the board.",
        },
        "card-5": {
            "id": "card-5",
            "title": "Design card layout",
            "details": "Add hierarchy and spacing for scanning dense lists.",
        },
        "card-6": {
            "id": "card-6",
            "title": "QA micro-interactions",
            "details": "Verify hover, focus, and loading states.",
        },
        "card-7": {
            "id": "card-7",
            "title": "Ship marketing page",
            "details": "Final copy approved and asset pack delivered.",
        },
        "card-8": {
            "id": "card-8",
            "title": "Close onboarding sprint",
            "details": "Document release notes and share internally.",
        },
    },
}


class VersionConflictError(Exception):
    def __init__(self, current_version: int):
        super().__init__("Board version conflict")
        self.current_version = current_version


def default_db_path() -> Path:
    configured = os.getenv("PM_DB_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "db.sqlite3"


def migration_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "db" / "migrations"


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _apply_migrations(connection: sqlite3.Connection) -> None:
    current_version = connection.execute("PRAGMA user_version").fetchone()[0]
    files = sorted(migration_dir().glob("*.sql"))

    for migration in files:
        version = int(migration.stem.split("_", 1)[0])
        if version <= current_version:
            continue
        connection.executescript(migration.read_text(encoding="utf-8"))
        connection.execute(f"PRAGMA user_version = {version}")
        current_version = version

    connection.commit()


def _bootstrap_mvp_data(connection: sqlite3.Connection) -> None:
    user_row = connection.execute(
        "SELECT id FROM users WHERE username = ?",
        (MVP_USERNAME,),
    ).fetchone()
    if user_row is None:
        cursor = connection.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (MVP_USERNAME, MVP_PASSWORD_HASH),
        )
        user_id = cursor.lastrowid
    else:
        user_id = user_row["id"]

    board_row = connection.execute(
        "SELECT id FROM boards WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if board_row is None:
        connection.execute(
            "INSERT INTO boards (user_id, board_json, version) VALUES (?, ?, 1)",
            (user_id, json.dumps(DEFAULT_BOARD)),
        )

    connection.commit()


def initialize_database(db_path: Path | None = None) -> Path:
    resolved_db_path = db_path or default_db_path()
    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = _connect(resolved_db_path)
    try:
        _apply_migrations(connection)
        _bootstrap_mvp_data(connection)
    finally:
        connection.close()

    return resolved_db_path


def get_board(username: str, db_path: Path | None = None) -> tuple[dict, int]:
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        row = connection.execute(
            """
            SELECT b.board_json, b.version
            FROM boards b
            JOIN users u ON u.id = b.user_id
            WHERE u.username = ?
            """,
            (username,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise KeyError(f"No board found for user {username}")

    return json.loads(row["board_json"]), row["version"]


def update_board(
    username: str,
    board: dict,
    expected_version: int | None,
    db_path: Path | None = None,
) -> int:
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT b.id, b.version
            FROM boards b
            JOIN users u ON u.id = b.user_id
            WHERE u.username = ?
            """,
            (username,),
        ).fetchone()

        if row is None:
            raise KeyError(f"No board found for user {username}")

        current_version = row["version"]
        if expected_version is not None and expected_version != current_version:
            connection.rollback()
            raise VersionConflictError(current_version=current_version)

        next_version = current_version + 1
        connection.execute(
            """
            UPDATE boards
            SET board_json = ?, version = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (json.dumps(board), next_version, row["id"]),
        )
        connection.commit()
        return next_version
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
