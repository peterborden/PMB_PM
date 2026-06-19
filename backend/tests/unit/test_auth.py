import pytest

from app.auth import (
    PBKDF2_ALGORITHM,
    generate_session_token,
    hash_password,
    verify_password,
)


def test_hash_is_self_describing_and_verifies() -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith(f"{PBKDF2_ALGORITHM}$")
    assert verify_password("correct horse battery staple", encoded)


def test_verify_rejects_wrong_password() -> None:
    encoded = hash_password("super-secret")
    assert not verify_password("not-the-password", encoded)


def test_hash_is_salted_so_two_hashes_differ() -> None:
    first = hash_password("same-password")
    second = hash_password("same-password")
    assert first != second
    assert verify_password("same-password", first)
    assert verify_password("same-password", second)


def test_empty_password_is_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("")


def test_verify_handles_malformed_hashes_gracefully() -> None:
    assert not verify_password("anything", "not-a-valid-hash")
    assert not verify_password("anything", "")
    assert not verify_password("anything", "a$b$c")  # too few segments


def test_session_tokens_are_unique_and_nonempty() -> None:
    tokens = {generate_session_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(token for token in tokens)
