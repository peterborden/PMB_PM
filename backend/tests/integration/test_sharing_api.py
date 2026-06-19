import copy

from fastapi.testclient import TestClient

from app.main import create_app


def _client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "test.db"))


def _register(client, username):
    return client.post(
        "/api/auth/register", json={"username": username, "password": "password123"}
    )


def _setup(tmp_path):
    """Alice (owner) shares nothing yet; returns alice client, bob client, board id."""
    alice = _client(tmp_path)
    _register(alice, "alice")
    board_id = alice.get("/api/boards").json()["boards"][0]["id"]

    bob = TestClient(create_app(db_path=tmp_path / "test.db"))
    _register(bob, "bob")
    return alice, bob, board_id


def test_share_grants_member_full_board_access(tmp_path) -> None:
    alice, bob, board_id = _setup(tmp_path)

    share = alice.post(f"/api/boards/{board_id}/members", json={"username": "bob"})
    assert share.status_code == 201
    assert share.json() == {"username": "bob", "role": "editor"}

    # Bob now sees the board with role editor and owner alice.
    bob_boards = bob.get("/api/boards").json()["boards"]
    shared = next(b for b in bob_boards if b["id"] == board_id)
    assert shared["role"] == "editor"
    assert shared["ownerUsername"] == "alice"

    # Bob can read and write it.
    detail = bob.get(f"/api/boards/{board_id}").json()
    updated = copy.deepcopy(detail["board"])
    updated["columns"][0]["title"] = "Bob was here"
    save = bob.put(
        f"/api/boards/{board_id}",
        json={"board": updated, "expectedVersion": detail["version"]},
    )
    assert save.status_code == 200
    # Alice sees Bob's edit.
    assert (
        alice.get(f"/api/boards/{board_id}").json()["board"]["columns"][0]["title"]
        == "Bob was here"
    )


def test_member_cannot_manage_or_remove_board(tmp_path) -> None:
    alice, bob, board_id = _setup(tmp_path)
    alice.post(f"/api/boards/{board_id}/members", json={"username": "bob"})

    # Members cannot rename, delete, or add other members.
    assert bob.patch(f"/api/boards/{board_id}", json={"name": "Hijack"}).status_code == 404
    assert bob.delete(f"/api/boards/{board_id}").status_code == 404
    assert (
        bob.post(f"/api/boards/{board_id}/members", json={"username": "alice"}).status_code
        == 404
    )


def test_list_members_visible_to_participants(tmp_path) -> None:
    alice, bob, board_id = _setup(tmp_path)
    alice.post(f"/api/boards/{board_id}/members", json={"username": "bob"})

    members = alice.get(f"/api/boards/{board_id}/members").json()["members"]
    assert {"username": "alice", "role": "owner"} in members
    assert {"username": "bob", "role": "editor"} in members
    # Bob (a member) can also view the member list.
    assert bob.get(f"/api/boards/{board_id}/members").status_code == 200


def test_share_validation_errors(tmp_path) -> None:
    alice, _bob, board_id = _setup(tmp_path)

    # Unknown user.
    assert (
        alice.post(f"/api/boards/{board_id}/members", json={"username": "ghost"}).status_code
        == 404
    )
    # Sharing with the owner is rejected.
    assert (
        alice.post(f"/api/boards/{board_id}/members", json={"username": "alice"}).status_code
        == 400
    )


def test_unshare_revokes_access(tmp_path) -> None:
    alice, bob, board_id = _setup(tmp_path)
    alice.post(f"/api/boards/{board_id}/members", json={"username": "bob"})
    assert bob.get(f"/api/boards/{board_id}").status_code == 200

    removed = alice.delete(f"/api/boards/{board_id}/members/bob")
    assert removed.status_code == 204
    assert bob.get(f"/api/boards/{board_id}").status_code == 404


def test_outsider_cannot_view_members(tmp_path) -> None:
    alice, _bob, board_id = _setup(tmp_path)
    carol = TestClient(create_app(db_path=tmp_path / "test.db"))
    _register(carol, "carol")
    assert carol.get(f"/api/boards/{board_id}/members").status_code == 404
