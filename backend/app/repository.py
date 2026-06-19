import json
import os
import sqlite3
from pathlib import Path

from .auth import generate_session_token, hash_password, verify_password

MVP_USERNAME = "user"
MVP_PASSWORD = "password"

SESSION_TTL_SECONDS = 60 * 60 * 24

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


def empty_board() -> dict:
    """A valid, empty starter board for newly created boards."""
    return {
        "columns": [
            {"id": "col-todo", "title": "To Do", "cardIds": []},
            {"id": "col-progress", "title": "In Progress", "cardIds": []},
            {"id": "col-done", "title": "Done", "cardIds": []},
        ],
        "cards": {},
    }


class VersionConflictError(Exception):
    def __init__(self, current_version: int):
        super().__init__("Board version conflict")
        self.current_version = current_version


class UsernameTakenError(Exception):
    def __init__(self, username: str):
        super().__init__(f"Username already taken: {username}")
        self.username = username


class BoardNotFoundError(Exception):
    def __init__(self, board_id: int):
        super().__init__(f"No board found with id {board_id}")
        self.board_id = board_id


class LastBoardError(Exception):
    def __init__(self) -> None:
        super().__init__("Cannot delete the only remaining board")


class UserNotFoundError(Exception):
    def __init__(self, username: str):
        super().__init__(f"No user found: {username}")
        self.username = username


class ShareError(Exception):
    """Raised for invalid sharing requests (e.g. sharing with the owner)."""


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


def _now_expr() -> str:
    return "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


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
        "SELECT id, password_hash FROM users WHERE username = ?",
        (MVP_USERNAME,),
    ).fetchone()
    if user_row is None:
        cursor = connection.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (MVP_USERNAME, hash_password(MVP_PASSWORD)),
        )
        user_id = cursor.lastrowid
    else:
        user_id = user_row["id"]
        # Heal seeded users created before real password hashing existed
        # (the old bootstrap stored a non-verifiable placeholder hash).
        if not str(user_row["password_hash"]).startswith("pbkdf2_sha256$"):
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(MVP_PASSWORD), user_id),
            )

    board_row = connection.execute(
        "SELECT id FROM boards WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if board_row is None:
        connection.execute(
            """
            INSERT INTO boards (user_id, name, position, board_json, version)
            VALUES (?, 'My Board', 0, ?, 1)
            """,
            (user_id, json.dumps(DEFAULT_BOARD)),
        )

    connection.commit()


_initialized_paths: set[Path] = set()


def initialize_database(db_path: Path | None = None) -> Path:
    resolved_db_path = db_path or default_db_path()
    if resolved_db_path in _initialized_paths:
        return resolved_db_path

    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = _connect(resolved_db_path)
    try:
        _apply_migrations(connection)
        _bootstrap_mvp_data(connection)
    finally:
        connection.close()

    _initialized_paths.add(resolved_db_path)
    return resolved_db_path


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def create_user(username: str, password: str, db_path: Path | None = None) -> int:
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing is not None:
            connection.rollback()
            raise UsernameTakenError(username)

        cursor = connection.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password)),
        )
        user_id = cursor.lastrowid
        connection.execute(
            """
            INSERT INTO boards (user_id, name, position, board_json, version)
            VALUES (?, 'My Board', 0, ?, 1)
            """,
            (user_id, json.dumps(DEFAULT_BOARD)),
        )
        connection.commit()
        return user_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_user_by_username(username: str, db_path: Path | None = None) -> dict | None:
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        row = connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        connection.close()
    return dict(row) if row is not None else None


def authenticate_user(
    username: str, password: str, db_path: Path | None = None
) -> dict | None:
    user = get_user_by_username(username, db_path=db_path)
    if user is None:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {"id": user["id"], "username": user["username"]}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def create_session(user_id: int, db_path: Path | None = None) -> str:
    resolved_db_path = initialize_database(db_path)
    token = generate_session_token()
    connection = _connect(resolved_db_path)
    try:
        connection.execute(
            f"""
            INSERT INTO sessions (token, user_id, expires_at)
            VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now', '+{SESSION_TTL_SECONDS} seconds'))
            """,
            (token, user_id),
        )
        connection.commit()
    finally:
        connection.close()
    return token


def get_session_user(token: str, db_path: Path | None = None) -> dict | None:
    if not token:
        return None
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        row = connection.execute(
            f"""
            SELECT u.id AS id, u.username AS username
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > {_now_expr()}
            """,
            (token,),
        ).fetchone()
    finally:
        connection.close()
    return dict(row) if row is not None else None


def delete_session(token: str, db_path: Path | None = None) -> None:
    if not token:
        return
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
        connection.commit()
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# Boards
# ---------------------------------------------------------------------------


def _board_meta_row_to_dict(
    row: sqlite3.Row, role: str = "owner", owner_username: str | None = None
) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "version": row["version"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "role": role,
        "ownerUsername": owner_username,
    }


def list_boards(user_id: int, db_path: Path | None = None) -> list[dict]:
    """Boards the user can access: those they own plus those shared with them.

    Owned boards come first (by position), then shared boards (by name). Each row
    carries the caller's role ('owner' or 'editor') and the owning username.
    """
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        rows = connection.execute(
            """
            SELECT b.id, b.name, b.version, b.created_at, b.updated_at,
                   ou.username AS owner_username,
                   CASE WHEN b.user_id = ? THEN 'owner' ELSE 'editor' END AS role
            FROM boards b
            JOIN users ou ON ou.id = b.user_id
            WHERE b.user_id = ?
               OR b.id IN (SELECT board_id FROM board_members WHERE user_id = ?)
            ORDER BY (b.user_id = ?) DESC, b.position ASC, b.name ASC, b.id ASC
            """,
            (user_id, user_id, user_id, user_id),
        ).fetchall()
    finally:
        connection.close()
    return [
        _board_meta_row_to_dict(row, role=row["role"], owner_username=row["owner_username"])
        for row in rows
    ]


def create_board(
    user_id: int,
    name: str,
    board: dict | None = None,
    db_path: Path | None = None,
) -> dict:
    resolved_db_path = initialize_database(db_path)
    board_json = json.dumps(board if board is not None else empty_board())
    connection = _connect(resolved_db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        position_row = connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_position FROM boards WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        next_position = position_row["next_position"]
        cursor = connection.execute(
            """
            INSERT INTO boards (user_id, name, position, board_json, version)
            VALUES (?, ?, ?, ?, 1)
            """,
            (user_id, name, next_position, board_json),
        )
        board_id = cursor.lastrowid
        row = connection.execute(
            """
            SELECT b.id, b.name, b.version, b.created_at, b.updated_at,
                   u.username AS owner_username
            FROM boards b JOIN users u ON u.id = b.user_id
            WHERE b.id = ?
            """,
            (board_id,),
        ).fetchone()
        connection.commit()
        return _board_meta_row_to_dict(row, owner_username=row["owner_username"])
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_board_by_id(
    board_id: int, user_id: int, db_path: Path | None = None
) -> tuple[dict, int, str]:
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        row = connection.execute(
            """
            SELECT board_json, version, name FROM boards
            WHERE id = ? AND (
                user_id = ?
                OR id IN (SELECT board_id FROM board_members WHERE user_id = ?)
            )
            """,
            (board_id, user_id, user_id),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise BoardNotFoundError(board_id)
    return json.loads(row["board_json"]), row["version"], row["name"]


def get_default_board_id(user_id: int, db_path: Path | None = None) -> int:
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        row = connection.execute(
            """
            SELECT id FROM boards
            WHERE user_id = ?
            ORDER BY position ASC, id ASC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise BoardNotFoundError(0)
    return row["id"]


def update_board_by_id(
    board_id: int,
    user_id: int,
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
            SELECT id, version FROM boards
            WHERE id = ? AND (
                user_id = ?
                OR id IN (SELECT board_id FROM board_members WHERE user_id = ?)
            )
            """,
            (board_id, user_id, user_id),
        ).fetchone()
        if row is None:
            connection.rollback()
            raise BoardNotFoundError(board_id)

        current_version = row["version"]
        if expected_version is not None and expected_version != current_version:
            connection.rollback()
            raise VersionConflictError(current_version=current_version)

        next_version = current_version + 1
        connection.execute(
            f"""
            UPDATE boards
            SET board_json = ?, version = ?, updated_at = {_now_expr()}
            WHERE id = ?
            """,
            (json.dumps(board), next_version, board_id),
        )
        connection.commit()
        return next_version
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def rename_board(
    board_id: int, user_id: int, name: str, db_path: Path | None = None
) -> dict:
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT id FROM boards WHERE id = ? AND user_id = ?",
            (board_id, user_id),
        ).fetchone()
        if row is None:
            connection.rollback()
            raise BoardNotFoundError(board_id)
        connection.execute(
            f"UPDATE boards SET name = ?, updated_at = {_now_expr()} WHERE id = ?",
            (name, board_id),
        )
        meta = connection.execute(
            """
            SELECT b.id, b.name, b.version, b.created_at, b.updated_at,
                   u.username AS owner_username
            FROM boards b JOIN users u ON u.id = b.user_id
            WHERE b.id = ?
            """,
            (board_id,),
        ).fetchone()
        connection.commit()
        return _board_meta_row_to_dict(meta, owner_username=meta["owner_username"])
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_board(board_id: int, user_id: int, db_path: Path | None = None) -> None:
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT id FROM boards WHERE id = ? AND user_id = ?",
            (board_id, user_id),
        ).fetchone()
        if row is None:
            connection.rollback()
            raise BoardNotFoundError(board_id)

        count_row = connection.execute(
            "SELECT COUNT(*) AS count FROM boards WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if count_row["count"] <= 1:
            connection.rollback()
            raise LastBoardError()

        connection.execute("DELETE FROM boards WHERE id = ?", (board_id,))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# Board members (sharing)
# ---------------------------------------------------------------------------


def _require_owned_board(connection: sqlite3.Connection, board_id: int, owner_id: int) -> None:
    row = connection.execute(
        "SELECT id FROM boards WHERE id = ? AND user_id = ?",
        (board_id, owner_id),
    ).fetchone()
    if row is None:
        raise BoardNotFoundError(board_id)


def add_board_member(
    board_id: int,
    owner_id: int,
    member_username: str,
    role: str = "editor",
    db_path: Path | None = None,
) -> dict:
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        _require_owned_board(connection, board_id, owner_id)

        member = connection.execute(
            "SELECT id, username FROM users WHERE username = ?",
            (member_username,),
        ).fetchone()
        if member is None:
            connection.rollback()
            raise UserNotFoundError(member_username)
        if member["id"] == owner_id:
            connection.rollback()
            raise ShareError("Cannot share a board with its owner")

        connection.execute(
            """
            INSERT INTO board_members (board_id, user_id, role)
            VALUES (?, ?, ?)
            ON CONFLICT(board_id, user_id) DO UPDATE SET role = excluded.role
            """,
            (board_id, member["id"], role),
        )
        connection.commit()
        return {"username": member["username"], "role": role}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_board_members(
    board_id: int, user_id: int, db_path: Path | None = None
) -> list[dict]:
    """Owner first (role 'owner'), then shared members. Any participant may view."""
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        board = connection.execute(
            """
            SELECT b.user_id AS owner_id, ou.username AS owner_username
            FROM boards b
            JOIN users ou ON ou.id = b.user_id
            WHERE b.id = ? AND (
                b.user_id = ?
                OR b.id IN (SELECT board_id FROM board_members WHERE user_id = ?)
            )
            """,
            (board_id, user_id, user_id),
        ).fetchone()
        if board is None:
            raise BoardNotFoundError(board_id)

        member_rows = connection.execute(
            """
            SELECT u.username AS username, m.role AS role
            FROM board_members m
            JOIN users u ON u.id = m.user_id
            WHERE m.board_id = ?
            ORDER BY u.username ASC
            """,
            (board_id,),
        ).fetchall()
    finally:
        connection.close()

    members = [{"username": board["owner_username"], "role": "owner"}]
    members.extend({"username": row["username"], "role": row["role"]} for row in member_rows)
    return members


def remove_board_member(
    board_id: int,
    owner_id: int,
    member_username: str,
    db_path: Path | None = None,
) -> None:
    resolved_db_path = initialize_database(db_path)
    connection = _connect(resolved_db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        _require_owned_board(connection, board_id, owner_id)

        member = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (member_username,),
        ).fetchone()
        if member is None:
            connection.rollback()
            raise UserNotFoundError(member_username)

        connection.execute(
            "DELETE FROM board_members WHERE board_id = ? AND user_id = ?",
            (board_id, member["id"]),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
