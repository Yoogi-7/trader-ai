from __future__ import annotations

import hashlib
import secrets

TOKEN_PREFIX_LENGTH = 12


def generate_token() -> str:
    """Generate a cryptographically secure API token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_token_prefix(token: str, length: int = TOKEN_PREFIX_LENGTH) -> str:
    """Return a non-secret prefix of the token for display purposes."""
    return token[:length]


__all__ = ["generate_token", "hash_token", "build_token_prefix", "TOKEN_PREFIX_LENGTH"]
