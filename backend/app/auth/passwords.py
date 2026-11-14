"""Password hashing with argon2id.

argon2id is deliberately slow and memory-hungry, so a leaked hash is expensive to
brute-force. These functions are CPU-bound (~tens of ms), so callers run them in a
worker thread (`asyncio.to_thread`) to keep the event loop free for other requests.
"""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # argon2id with the library's recommended parameters

# Used when the email doesn't exist, so "unknown email" takes as long as
# "wrong password" and response timing can't reveal which accounts exist.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def burn_verify_time(password: str) -> None:
    verify_password(_DUMMY_HASH, password)
