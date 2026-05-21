"""Symmetric encryption for secrets at rest (per-user API keys).

The Fernet key is derived from ``SECRET_KEY`` (SHA-256 → 32 bytes → urlsafe
base64), so no extra env var is needed — the same secret that signs JWTs also
encrypts stored keys. Rotating ``SECRET_KEY`` invalidates stored ciphertext
(users simply re-enter their keys), which is acceptable.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from config import get_settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    secret = get_settings().secret_key.encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str | None:
    """Returns the plaintext, or None if the token can't be decrypted
    (wrong/rotated key, corrupted value)."""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError):
        return None
