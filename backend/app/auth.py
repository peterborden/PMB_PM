"""Password hashing and session-token helpers.

Uses only the standard library: PBKDF2-HMAC-SHA256 for passwords (no external
dependency) and ``secrets`` for session tokens. Password hashes are stored in a
self-describing ``algo$iterations$salt$hash`` string so the work factor can be
raised later without invalidating existing hashes.
"""

import base64
import hashlib
import hmac
import secrets

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 200_000
SALT_BYTES = 16
SESSION_TOKEN_BYTES = 32


def _b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64decode(encoded: str) -> bytes:
    return base64.b64decode(encoded.encode("ascii"))


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    if not password:
        raise ValueError("Password must not be empty")
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return "$".join(
        [PBKDF2_ALGORITHM, str(PBKDF2_ITERATIONS), _b64encode(salt), _b64encode(derived)]
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_b64, hash_b64 = encoded.split("$")
        if algorithm != PBKDF2_ALGORITHM:
            return False
        iterations = int(iterations_text)
        salt = _b64decode(salt_b64)
        expected = _b64decode(hash_b64)
    except (ValueError, base64.binascii.Error):
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(derived, expected)


def generate_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)
