import pytest

from app.repository import (
    BoardNotFoundError,
    ShareError,
    UserNotFoundError,
    add_board_member,
    create_user,
    get_board_by_id,
    list_board_members,
    list_boards,
    remove_board_member,
    update_board_by_id,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


def _setup_two_users(db_path):
    alice = create_user("alice", "password123", db_path=db_path)
    bob = create_user("bob", "password123", db_path=db_path)
    alice_board = list_boards(alice, db_path=db_path)[0]["id"]
    return alice, bob, alice_board


def test_member_can_read_and_write_shared_board(db_path) -> None:
    alice, bob, board_id = _setup_two_users(db_path)
    add_board_member(board_id, alice, "bob", db_path=db_path)

    data, version, name = get_board_by_id(board_id, bob, db_path=db_path)
    assert name == "My Board"
    # Member can write.
    new_version = update_board_by_id(
        board_id, bob, board=data, expected_version=version, db_path=db_path
    )
    assert new_version == version + 1


def test_shared_board_appears_in_member_board_list(db_path) -> None:
    alice, bob, board_id = _setup_two_users(db_path)
    add_board_member(board_id, alice, "bob", db_path=db_path)

    boards = list_boards(bob, db_path=db_path)
    # Bob's own default board plus Alice's shared board.
    shared = next(entry for entry in boards if entry["id"] == board_id)
    assert shared["role"] == "editor"
    assert shared["ownerUsername"] == "alice"

    owned = next(entry for entry in boards if entry["id"] != board_id)
    assert owned["role"] == "owner"
    assert owned["ownerUsername"] == "bob"


def test_non_member_cannot_access(db_path) -> None:
    _alice, bob, board_id = _setup_two_users(db_path)
    with pytest.raises(BoardNotFoundError):
        get_board_by_id(board_id, bob, db_path=db_path)


def test_add_member_rejects_unknown_user(db_path) -> None:
    alice, _bob, board_id = _setup_two_users(db_path)
    with pytest.raises(UserNotFoundError):
        add_board_member(board_id, alice, "nobody", db_path=db_path)


def test_cannot_share_with_owner(db_path) -> None:
    alice, _bob, board_id = _setup_two_users(db_path)
    with pytest.raises(ShareError):
        add_board_member(board_id, alice, "alice", db_path=db_path)


def test_only_owner_can_add_members(db_path) -> None:
    alice, bob, board_id = _setup_two_users(db_path)
    add_board_member(board_id, alice, "bob", db_path=db_path)
    # Bob is a member, not the owner, so he cannot add others.
    create_user("carol", "password123", db_path=db_path)
    with pytest.raises(BoardNotFoundError):
        add_board_member(board_id, bob, "carol", db_path=db_path)


def test_remove_member_revokes_access(db_path) -> None:
    alice, bob, board_id = _setup_two_users(db_path)
    add_board_member(board_id, alice, "bob", db_path=db_path)
    get_board_by_id(board_id, bob, db_path=db_path)  # has access

    remove_board_member(board_id, alice, "bob", db_path=db_path)
    with pytest.raises(BoardNotFoundError):
        get_board_by_id(board_id, bob, db_path=db_path)


def test_list_members_returns_owner_first(db_path) -> None:
    alice, _bob, board_id = _setup_two_users(db_path)
    add_board_member(board_id, alice, "bob", db_path=db_path)

    members = list_board_members(board_id, alice, db_path=db_path)
    assert members[0] == {"username": "alice", "role": "owner"}
    assert {"username": "bob", "role": "editor"} in members


def test_adding_existing_member_is_idempotent(db_path) -> None:
    alice, _bob, board_id = _setup_two_users(db_path)
    add_board_member(board_id, alice, "bob", db_path=db_path)
    add_board_member(board_id, alice, "bob", db_path=db_path)
    members = list_board_members(board_id, alice, db_path=db_path)
    assert sum(1 for m in members if m["username"] == "bob") == 1
