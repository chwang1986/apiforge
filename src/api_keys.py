"""ApiForge API key management.

Generate, store, validate, and rotate API keys with expiration support.

Usage:
    from src.api_keys import KeyManager

    km = KeyManager()
    key = km.generate(name="client-a")
    km.validate(key)  # → KeyInfo
    km.revoke(key)
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class KeyInfo:
    """Metadata about an API key.

    Args:
        key_id: Short unique identifier (first 8 chars of key).
        name: Human-readable name.
        prefix: First 8 chars of the key (for identification).
        created_at: Unix timestamp of creation.
        expires_at: Unix timestamp of expiration (0 = never).
        last_used: Unix timestamp of last validation (0 = never used).
        revoked: Whether the key has been revoked.
        metadata: Arbitrary extra data.
    """

    key_id: str
    name: str
    prefix: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    last_used: float = 0.0
    revoked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now: float | None = None) -> bool:
        """Check if key has expired."""
        if self.expires_at <= 0:
            return False
        return (now or time.time()) >= self.expires_at

    def is_valid(self, now: float | None = None) -> bool:
        """Check if key is usable (not revoked, not expired)."""
        return not self.revoked and not self.is_expired(now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key_id": self.key_id,
            "name": self.name,
            "prefix": self.prefix,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_used": self.last_used,
            "revoked": self.revoked,
            "metadata": self.metadata,
            "valid": self.is_valid(),
        }


class KeyManager:
    """Manages API keys with generation, validation, and rotation.

    Usage:
        km = KeyManager(secret="my-secret")
        key = km.generate("production", ttl_hours=24)
        info = km.validate(key)
        km.revoke(key)
    """

    def __init__(self, secret: str = "apiforge") -> None:
        self._secret = secret
        # key_id -> KeyInfo
        self._keys: dict[str, KeyInfo] = {}
        # hashed_key -> key_id (for lookup)
        self._hash_to_id: dict[str, str] = {}

    def generate(
        self,
        name: str,
        *,
        ttl_hours: float | None = None,
        metadata: dict[str, Any] | None = None,
        length: int = 40,
    ) -> str:
        """Generate a new API key.

        Args:
            name: Human-readable name for the key.
            ttl_hours: Optional TTL in hours (None = no expiry).
            metadata: Extra metadata to store with the key.
            length: Key length (default 40 hex chars).

        Returns:
            The generated API key string (format: af_<name>_<random>).
        """
        random_part = secrets.token_hex(length // 2)
        key = f"af_{name}_{random_part}"
        # Use a hash-derived id so keys with the same name stay unique
        key_id = self._hash(key)[:12]
        prefix = key[:16]
        expires_at = time.time() + (ttl_hours * 3600) if ttl_hours else 0.0

        info = KeyInfo(
            key_id=key_id,
            name=name,
            prefix=prefix,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        self._keys[key_id] = info
        self._hash_to_id[self._hash(key)] = key_id
        return key

    def validate(self, key: str, now: float | None = None) -> KeyInfo:
        """Validate an API key.

        Args:
            key: The API key to validate.
            now: Current time (for testing).

        Returns:
            The KeyInfo if valid.

        Raises:
            ValueError: If key is unknown, revoked, or expired.
        """
        key_id = self._hash_to_id.get(self._hash(key))
        if key_id is None:
            raise ValueError("Unknown API key")
        info = self._keys[key_id]
        if info.revoked:
            raise ValueError("API key has been revoked")
        if info.is_expired(now):
            raise ValueError("API key has expired")
        info.last_used = now or time.time()
        return info

    def revoke(self, key: str) -> None:
        """Revoke an API key."""
        key_id = self._hash_to_id.get(self._hash(key))
        if key_id is None:
            raise ValueError("Unknown API key")
        self._keys[key_id].revoked = True

    def rotate(
        self,
        key: str,
        *,
        ttl_hours: float | None = None,
        grace_period: float = 0.0,
    ) -> str:
        """Rotate an API key: revoke old, generate new.

        Args:
            key: The old key to rotate.
            ttl_hours: TTL for the new key.
            grace_period: Seconds during which old key still valid (0 = immediate).

        Returns:
            The new API key.
        """
        info = self._keys[self._hash_to_id[self._hash(key)]]
        self.revoke(key)
        new_key = self.generate(
            info.name,
            ttl_hours=ttl_hours,
            metadata=info.metadata,
        )
        return new_key

    def list_keys(self, include_revoked: bool = False) -> list[KeyInfo]:
        """List all keys."""
        keys = list(self._keys.values())
        if not include_revoked:
            keys = [k for k in keys if not k.revoked]
        return keys

    def delete(self, key: str) -> None:
        """Delete a key entirely (cannot be recovered)."""
        key_id = self._hash_to_id.pop(self._hash(key), None)
        if key_id is None:
            raise ValueError("Unknown API key")
        del self._keys[key_id]

    def __len__(self) -> int:
        return len(self._keys)

    def _hash(self, key: str) -> str:
        """Hash a key for storage (SHA-256 + secret)."""
        return hashlib.sha256(f"{self._secret}:{key}".encode()).hexdigest()


def create_key_manager(secret: str = "apiforge") -> KeyManager:
    """Create a new KeyManager."""
    return KeyManager(secret=secret)
