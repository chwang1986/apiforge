"""ApiForge configuration system.

Provides a layered configuration system following the 12-Factor App principles:
  1. Code defaults (lowest priority)
  2. .env file
  3. Environment variables (highest priority)

Usage:
    from src.config import Settings

    settings = Settings()
    print(settings.host)       # "0.0.0.0"
    print(settings.port)       # 8000
    print(settings.debug)      # False

    # Override via env:
    # export APIFORGE_PORT=9000
    # export APIFORGE_DEBUG=true

    # Or in .env file:
    # APIFORGE_PORT=9000
    # APIFORGE_DEBUG=true
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def load_dotenv(path: str | Path = ".env") -> dict[str, str]:
    """Load key=value pairs from a .env file.

    Simple parser (no python-dotenv dependency):
    - Supports KEY=VALUE lines
    - Ignores comments (#) and empty lines
    - Strips optional quotes around values
    - Does NOT override existing env vars

    Args:
        path: Path to the .env file.

    Returns:
        Dict of key-value pairs loaded from the file.
    """
    env_file = Path(path)
    if not env_file.exists():
        return {}

    loaded: dict[str, str] = {}
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Split on first =
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            # Don't override existing env vars
            if key not in os.environ:
                loaded[key] = value

    # Apply to os.environ (without overriding)
    for k, v in loaded.items():
        if k not in os.environ:
            os.environ[k] = v

    return loaded


def _env_str(key: str, default: str = "") -> str:
    """Get a string env var."""
    return os.environ.get(f"APIFORGE_{key}", os.environ.get(key, default))


def _env_int(key: str, default: int) -> int:
    """Get an int env var."""
    val = os.environ.get(f"APIFORGE_{key}", os.environ.get(key, ""))
    if val:
        try:
            return int(val)
        except ValueError:
            pass
    return default


def _env_bool(key: str, default: bool = False) -> bool:
    """Get a bool env var (true/1/yes/on)."""
    val = os.environ.get(f"APIFORGE_{key}", os.environ.get(key, "")).lower()
    if val in ("true", "1", "yes", "on"):
        return True
    if val in ("false", "0", "no", "off", ""):
        return False
    return default


def _env_list(key: str, default: list[str] | None = None) -> list[str] | None:
    """Get a comma-separated list env var."""
    val = os.environ.get(f"APIFORGE_{key}", os.environ.get(key, ""))
    if val:
        return [v.strip() for v in val.split(",") if v.strip()]
    return default


@dataclass
class Settings:
    """ApiForge application settings.

    All values can be overridden via environment variables
    (prefixed with APIFORGE_) or a .env file.

    Environment variable mapping:
        host       → APIFORGE_HOST
        port       → APIFORGE_PORT
        debug      → APIFORGE_DEBUG
        log_level  → APIFORGE_LOG_LEVEL
        cors_origins → APIFORGE_CORS_ORIGINS (comma-separated)
    """

    # --- Server ---
    host: str = field(default_factory=lambda: _env_str("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("PORT", 8000))
    debug: bool = field(default_factory=lambda: _env_bool("DEBUG", False))
    log_level: str = field(default_factory=lambda: _env_str("LOG_LEVEL", "info"))

    # --- Middleware ---
    cors_origins: list[str] | None = field(
        default_factory=lambda: _env_list("CORS_ORIGINS")
    )
    rate_limit_requests: int | None = field(
        default_factory=lambda: _env_int("RATE_LIMIT_REQUESTS", 0) or None
    )
    rate_limit_window: int = field(
        default_factory=lambda: _env_int("RATE_LIMIT_WINDOW", 60)
    )

    # --- Auth ---
    api_keys: str | None = field(
        default_factory=lambda: _env_str("API_KEYS", "") or None
    )
    """Comma-separated key:client pairs, e.g. 'key1:clientA,key2:clientB'"""

    # --- Features ---
    envelope: bool = field(default_factory=lambda: _env_bool("ENVELOPE", False))

    @property
    def api_keys_dict(self) -> dict[str, str] | None:
        """Parse api_keys string into dict."""
        if not self.api_keys:
            return None
        result: dict[str, str] = {}
        for pair in self.api_keys.split(","):
            if ":" in pair:
                key, _, client = pair.partition(":")
                result[key.strip()] = client.strip()
            else:
                result[pair.strip()] = "unknown"
        return result if result else None

    @classmethod
    def from_env(cls, dotenv_path: str | Path = ".env") -> Settings:
        """Create Settings, loading .env file first (if exists).

        Args:
            dotenv_path: Path to .env file.

        Returns:
            Populated Settings instance.
        """
        load_dotenv(dotenv_path)
        return cls()


def load_settings(dotenv_path: str | Path = ".env") -> Settings:
    """Convenience: load .env and return Settings."""
    return Settings.from_env(dotenv_path)
