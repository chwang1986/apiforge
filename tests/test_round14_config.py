"""Round 14: Configuration system tests."""

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from src.config import Settings, load_dotenv, load_settings
from src.server import ApiForge


# --- Settings defaults ---

def test_settings_defaults() -> None:
    """Settings has sensible defaults when no env vars set."""
    # Clear any APIFORGE_* vars
    for key in list(os.environ):
        if key.startswith("APIFORGE_"):
            del os.environ[key]

    s = Settings()
    assert s.host == "0.0.0.0"
    assert s.port == 8000
    assert s.debug is False
    assert s.log_level == "info"
    assert s.envelope is False


# --- Settings from env vars ---

def test_settings_from_env() -> None:
    """Settings reads from APIFORGE_* env vars."""
    os.environ["APIFORGE_HOST"] = "127.0.0.1"
    os.environ["APIFORGE_PORT"] = "9000"
    os.environ["APIFORGE_DEBUG"] = "true"
    os.environ["APIFORGE_LOG_LEVEL"] = "debug"

    try:
        s = Settings()
        assert s.host == "127.0.0.1"
        assert s.port == 9000
        assert s.debug is True
        assert s.log_level == "debug"
    finally:
        del os.environ["APIFORGE_HOST"]
        del os.environ["APIFORGE_PORT"]
        del os.environ["APIFORGE_DEBUG"]
        del os.environ["APIFORGE_LOG_LEVEL"]


# --- Settings: CORS origins from env ---

def test_settings_cors_origins() -> None:
    """CORS origins parsed from comma-separated env var."""
    os.environ["APIFORGE_CORS_ORIGINS"] = "https://a.com,https://b.com"

    try:
        s = Settings()
        assert s.cors_origins == ["https://a.com", "https://b.com"]
    finally:
        del os.environ["APIFORGE_CORS_ORIGINS"]


# --- Settings: API keys parsing ---

def test_settings_api_keys() -> None:
    """API keys parsed from 'key:client' pairs."""
    os.environ["APIFORGE_API_KEYS"] = "key1:clientA,key2:clientB"

    try:
        s = Settings()
        assert s.api_keys_dict == {"key1": "clientA", "key2": "clientB"}
    finally:
        del os.environ["APIFORGE_API_KEYS"]


def test_settings_api_keys_none() -> None:
    """No API keys → None."""
    if "APIFORGE_API_KEYS" in os.environ:
        del os.environ["APIFORGE_API_KEYS"]
    s = Settings()
    assert s.api_keys_dict is None


# --- .env file loading ---

def test_load_dotenv_file(tmp_path: Path) -> None:
    """Load key-value pairs from a .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Comment line\n"
        "APIFORGE_HOST=192.168.1.1\n"
        "APIFORGE_PORT=7777\n"
        "APIFORGE_DEBUG=true\n"
        'APIFORGE_LOG_LEVEL="warning"\n'
        "EMPTY_VAL=\n"
        "   \n"
        "   # indented comment\n"
    )

    # Clean up
    for key in list(os.environ):
        if key.startswith("APIFORGE_"):
            del os.environ[key]

    loaded = load_dotenv(env_file)
    assert loaded["APIFORGE_HOST"] == "192.168.1.1"
    assert loaded["APIFORGE_PORT"] == "7777"
    assert loaded["APIFORGE_DEBUG"] == "true"
    assert loaded["APIFORGE_LOG_LEVEL"] == "warning"  # quotes stripped

    # Verify applied to os.environ
    assert os.environ["APIFORGE_HOST"] == "192.168.1.1"

    # Cleanup
    for k in list(os.environ):
        if k.startswith("APIFORGE_"):
            del os.environ[k]


def test_load_dotenv_missing_file() -> None:
    """Missing .env file returns empty dict."""
    result = load_dotenv("/nonexistent/path/.env")
    assert result == {}


def test_load_dotenv_does_not_override() -> None:
    """Existing env vars are NOT overridden by .env file."""
    tmp_path = Path("/tmp/test_apiforge_env")
    tmp_path.mkdir(parents=True, exist_ok=True)
    env_file = tmp_path / ".env"
    env_file.write_text("APIFORGE_HOST=from_file\n")

    os.environ["APIFORGE_HOST"] = "from_real_env"

    load_dotenv(env_file)
    # Real env should win
    assert os.environ["APIFORGE_HOST"] == "from_real_env"

    # Cleanup
    del os.environ["APIFORGE_HOST"]
    env_file.unlink(missing_ok=True)


# --- Settings.from_env ---

def test_settings_from_env_with_dotenv(tmp_path: Path) -> None:
    """Settings.from_env loads .env then applies defaults."""
    env_file = tmp_path / ".env"
    env_file.write_text("APIFORGE_PORT=12345\n")

    for key in list(os.environ):
        if key.startswith("APIFORGE_"):
            del os.environ[key]

    s = Settings.from_env(env_file)
    assert s.port == 12345
    assert s.host == "0.0.0.0"  # default

    # Cleanup
    for k in list(os.environ):
        if k.startswith("APIFORGE_"):
            del os.environ[k]


# --- Integration: ApiForge with config ---

def test_apiforge_respects_env_port() -> None:
    """ApiForge can use settings for port (conceptual test)."""
    os.environ["APIFORGE_PORT"] = "9999"
    try:
        s = Settings()
        assert s.port == 9999
        # ApiForge would use this: forge.run(port=s.port)
    finally:
        del os.environ["APIFORGE_PORT"]


# --- Bool parsing edge cases ---

def test_bool_parsing_variants() -> None:
    """Various truthy/falsy string values."""
    os.environ["APIFORGE_DEBUG"] = "1"
    assert Settings().debug is True

    os.environ["APIFORGE_DEBUG"] = "yes"
    assert Settings().debug is True

    os.environ["APIFORGE_DEBUG"] = "off"
    assert Settings().debug is False

    os.environ["APIFORGE_DEBUG"] = "0"
    assert Settings().debug is False

    del os.environ["APIFORGE_DEBUG"]
