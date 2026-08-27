"""Round 39: API key management tests."""

import time
import pytest

from src.api_keys import KeyInfo, KeyManager, create_key_manager


# --- KeyInfo dataclass ---

def test_key_info_fields() -> None:
    k = KeyInfo(key_id="abc123", name="test", prefix="af_test")
    assert k.key_id == "abc123"
    assert k.name == "test"
    assert k.prefix == "af_test"
    assert k.revoked is False
    assert k.created_at > 0


def test_key_info_is_expired() -> None:
    k = KeyInfo(key_id="x", name="n", prefix="p")
    assert k.is_expired() is False  # no expiry set

    k.expires_at = time.time() - 10  # expired 10s ago
    assert k.is_expired() is True

    k.expires_at = time.time() + 3600  # expires in 1h
    assert k.is_expired() is False


def test_key_info_is_valid() -> None:
    k = KeyInfo(key_id="x", name="n", prefix="p")
    assert k.is_valid() is True

    k.revoked = True
    assert k.is_valid() is False

    k2 = KeyInfo(key_id="y", name="n", prefix="p")
    k2.expires_at = time.time() - 5
    assert k2.is_valid() is False


def test_key_info_to_dict() -> None:
    k = KeyInfo(key_id="id1", name="client", prefix="af_client")
    d = k.to_dict()
    assert d["key_id"] == "id1"
    assert d["name"] == "client"
    assert d["valid"] is True


# --- KeyManager generate ---

def test_generate_key_format() -> None:
    km = KeyManager()
    key = km.generate("client-a")
    assert key.startswith("af_client-a_")
    assert len(key) > 20


def test_generate_key_unique() -> None:
    km = KeyManager()
    k1 = km.generate("c")
    k2 = km.generate("c")
    assert k1 != k2


def test_generate_with_ttl() -> None:
    km = KeyManager()
    key = km.generate("temp", ttl_hours=1)
    info = km.validate(key)
    assert info.expires_at > time.time()
    assert info.expires_at < time.time() + 3601


# --- KeyManager validate ---

def test_validate_returns_info() -> None:
    km = KeyManager()
    key = km.generate("prod")
    info = km.validate(key)
    assert info.name == "prod"
    assert info.last_used > 0


def test_validate_unknown_key_raises() -> None:
    km = KeyManager()
    with pytest.raises(ValueError, match="Unknown"):
        km.validate("af_fake_0000000")


def test_validate_revoked_raises() -> None:
    km = KeyManager()
    key = km.generate("x")
    km.revoke(key)
    with pytest.raises(ValueError, match="revoked"):
        km.validate(key)


def test_validate_expired_raises() -> None:
    km = KeyManager()
    key = km.generate("exp", ttl_hours=0.0001)  # expires almost immediately
    time.sleep(0.01)
    # Manually expire
    key_id = km._hash_to_id[km._hash(key)]
    km._keys[key_id].expires_at = time.time() - 1
    with pytest.raises(ValueError, match="expired"):
        km.validate(key)


# --- Revoke ---

def test_revoke_key() -> None:
    km = KeyManager()
    key = km.generate("r")
    km.revoke(key)
    info = km._keys[km._hash_to_id[km._hash(key)]]
    assert info.revoked is True


def test_revoke_unknown_raises() -> None:
    km = KeyManager()
    with pytest.raises(ValueError, match="Unknown"):
        km.revoke("af_nonexistent")


# --- Rotate ---

def test_rotate_generates_new_key() -> None:
    km = KeyManager()
    old_key = km.generate("rot")
    new_key = km.rotate(old_key)
    assert new_key != old_key
    # Old key is revoked
    with pytest.raises(ValueError):
        km.validate(old_key)
    # New key works
    info = km.validate(new_key)
    assert info.name == "rot"


# --- List / Delete ---

def test_list_keys() -> None:
    km = KeyManager()
    km.generate("a")
    km.generate("b")
    km.generate("c")
    assert len(km.list_keys()) == 3

    # Revoke one
    key_a = km.list_keys()[0]
    # Find the actual key string
    # list_keys returns KeyInfo, not key strings; use _keys directly
    assert len(km) == 3


def test_delete_key() -> None:
    km = KeyManager()
    key = km.generate("del")
    assert len(km) == 1
    km.delete(key)
    assert len(km) == 0


def test_delete_unknown_raises() -> None:
    km = KeyManager()
    with pytest.raises(ValueError):
        km.delete("af_missing")


# --- create_key_manager factory ---

def test_create_key_manager() -> None:
    km = create_key_manager(secret="s3cret")
    key = km.generate("x")
    assert km.validate(key).name == "x"
