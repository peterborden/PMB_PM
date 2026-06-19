import pytest

from app.repository import (
    BoardNotFoundError,
    LastBoardError,
    UsernameTakenError,
    VersionConflictError,
    authenticate_user,
    create_board,
    create_session,
    create_user,
    delete_board,
    delete_session,
    get_board_by_id,
    get_default_board_id,
    get_session_user,
    list_boards,
    rename_board,
    update_board_by_id,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


def test_create_user_creates_a_default_board(db_path) -> None:
    user_id = create_user("alice", "password123", db_path=db_path)
    boards = list_boards(user_id, db_path=db_path)
    assert len(boards) == 1
    assert boards[0]["name"] == "My Board"
    assert boards[0]["version"] == 1


def test_create_user_rejects_duplicate_username(db_path) -> None:
    create_user("alice", "password123", db_path=db_path)
    with pytest.raises(UsernameTakenError):
        create_user("alice", "different", db_path=db_path)


def test_authenticate_user_round_trips(db_path) -> None:
    create_user("alice", "password123", db_path=db_path)
    user = authenticate_user("alice", "password123", db_path=db_path)
    assert user is not None
    assert user["username"] == "alice"
    assert authenticate_user("alice", "wrong", db_path=db_path) is None
    assert authenticate_user("nobody", "password123", db_path=db_path) is None


def test_sessions_resolve_and_can_be_deleted(db_path) -> None:
    user_id = create_user("alice", "password123", db_path=db_path)
    token = create_session(user_id, db_path=db_path)
    resolved = get_session_user(token, db_path=db_path)
    assert resolved is not None
    assert resolved["username"] == "alice"

    delete_session(token, db_path=db_path)
    assert get_session_user(token, db_path=db_path) is None


def test_get_session_user_rejects_unknown_token(db_path) -> None:
    create_user("alice", "password123", db_path=db_path)
    assert get_session_user("does-not-exist", db_path=db_path) is None
    assert get_session_user("", db_path=db_path) is None


def test_expired_sessions_do_not_resolve(db_path) -> None:
    import sqlite3

    user_id = create_user("alice", "password123", db_path=db_path)
    token = create_session(user_id, db_path=db_path)
    # Force the session into the past.
    connection = sqlite3.connect(db_path)
    connection.execute(
        "UPDATE sessions SET expires_at = '2000-01-01T00:00:00.000Z' WHERE token = ?",
        (token,),
    )
    connection.commit()
    connection.close()
    assert get_session_user(token, db_path=db_path) is None


def test_boards_are_isolated_between_users(db_path) -> None:
    alice = create_user("alice", "password123", db_path=db_path)
    bob = create_user("bob", "password123", db_path=db_path)

    alice_board = list_boards(alice, db_path=db_path)[0]["id"]

    # Bob cannot read Alice's board.
    with pytest.raises(BoardNotFoundError):
        get_board_by_id(alice_board, bob, db_path=db_path)


def test_create_board_appends_with_increasing_position(db_path) -> None:
    user_id = create_user("alice", "password123", db_path=db_path)
    second = create_board(user_id, "Roadmap", db_path=db_path)
    third = create_board(user_id, "Bugs", db_path=db_path)

    boards = list_boards(user_id, db_path=db_path)
    assert [board["name"] for board in boards] == ["My Board", "Roadmap", "Bugs"]
    assert second["id"] != third["id"]

    board_data, version, name = get_board_by_id(second["id"], user_id, db_path=db_path)
    assert name == "Roadmap"
    assert version == 1
    assert board_data["cards"] == {}


def test_update_board_increments_version_and_checks_conflicts(db_path) -> None:
    user_id = create_user("alice", "password123", db_path=db_path)
    board_id = list_boards(user_id, db_path=db_path)[0]["id"]
    board_data, version, _ = get_board_by_id(board_id, user_id, db_path=db_path)

    new_version = update_board_by_id(
        board_id, user_id, board=board_data, expected_version=version, db_path=db_path
    )
    assert new_version == version + 1

    with pytest.raises(VersionConflictError):
        update_board_by_id(
            board_id, user_id, board=board_data, expected_version=version, db_path=db_path
        )


def test_update_board_rejects_foreign_board(db_path) -> None:
    alice = create_user("alice", "password123", db_path=db_path)
    bob = create_user("bob", "password123", db_path=db_path)
    alice_board = list_boards(alice, db_path=db_path)[0]["id"]
    data, version, _ = get_board_by_id(alice_board, alice, db_path=db_path)

    with pytest.raises(BoardNotFoundError):
        update_board_by_id(
            alice_board, bob, board=data, expected_version=version, db_path=db_path
        )


def test_rename_board(db_path) -> None:
    user_id = create_user("alice", "password123", db_path=db_path)
    board_id = list_boards(user_id, db_path=db_path)[0]["id"]
    meta = rename_board(board_id, user_id, "Renamed", db_path=db_path)
    assert meta["name"] == "Renamed"
    assert list_boards(user_id, db_path=db_path)[0]["name"] == "Renamed"


def test_delete_board_blocks_removing_the_last_board(db_path) -> None:
    user_id = create_user("alice", "password123", db_path=db_path)
    only_board = list_boards(user_id, db_path=db_path)[0]["id"]
    with pytest.raises(LastBoardError):
        delete_board(only_board, user_id, db_path=db_path)


def test_delete_board_removes_extra_boards(db_path) -> None:
    user_id = create_user("alice", "password123", db_path=db_path)
    extra = create_board(user_id, "Scratch", db_path=db_path)
    delete_board(extra["id"], user_id, db_path=db_path)
    assert len(list_boards(user_id, db_path=db_path)) == 1


def test_get_default_board_id_returns_first_board(db_path) -> None:
    user_id = create_user("alice", "password123", db_path=db_path)
    create_board(user_id, "Second", db_path=db_path)
    default_id = get_default_board_id(user_id, db_path=db_path)
    assert default_id == list_boards(user_id, db_path=db_path)[0]["id"]
