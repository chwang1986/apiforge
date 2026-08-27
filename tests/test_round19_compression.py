"""Round 19: Response compression (gzip) tests.

Note: httpx TestClient automatically:
- Sends Accept-Encoding: gzip
- Decompresses gzip responses transparently
So we verify compression via headers, not raw bytes.
"""

import pytest
from fastapi.testclient import TestClient

from src.server import ApiForge
from src.middleware.compression import enable_compression, DEFAULT_MINIMUM_SIZE


# --- Compression enabled: large response ---

def test_large_response_gzip_header() -> None:
    """Large response gets Content-Encoding: gzip header."""
    f = ApiForge(name="Compress", compress=True)

    @f.tool
    def big_data() -> str:
        """Return a large string."""
        return "A" * 10000

    c = TestClient(f.app)
    resp = c.post("/tools/big_data", json={})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"
    # httpx auto-decompresses, body is JSON (string wrapped in quotes)
    assert resp.json() == "A" * 10000
    # Vary header present (standard for compression)
    assert "accept-encoding" in resp.headers.get("vary", "").lower()


# --- Compression disabled ---

def test_compression_disabled() -> None:
    """Without compress=True, no compression even for large responses."""
    f = ApiForge(name="NoCompress", compress=False)

    @f.tool
    def big_data() -> str:
        """Return a large string."""
        return "B" * 10000

    c = TestClient(f.app)
    resp = c.post("/tools/big_data", json={})
    assert resp.status_code == 200
    # No compression middleware → no content-encoding header
    assert resp.headers.get("content-encoding") is None
    assert resp.json() == "B" * 10000


# --- Default minimum size ---

def test_default_minimum_size() -> None:
    """Default minimum compression size is 500 bytes."""
    assert DEFAULT_MINIMUM_SIZE == 500


# --- Compression works with other middleware ---

def test_compression_with_request_id() -> None:
    """Gzip works alongside request ID middleware."""
    f = ApiForge(name="Compress+RID", compress=True)

    @f.tool
    def big() -> str:
        """Large response."""
        return "D" * 10000

    c = TestClient(f.app)
    resp = c.post("/tools/big", json={})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"
    assert "x-request-id" in resp.headers


def test_compression_with_envelope() -> None:
    """Gzip works with response envelope."""
    f = ApiForge(name="Compress+Env", compress=True, envelope=True)

    @f.tool
    def big() -> str:
        """Large response."""
        return "E" * 10000

    c = TestClient(f.app)
    resp = c.post("/tools/big", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["data"]) == 10000
    assert resp.headers.get("content-encoding") == "gzip"


# --- JSON responses compress well ---

def test_json_response_compressed() -> None:
    """JSON responses above minimum size get compressed."""
    f = ApiForge(name="JSON", compress=True)

    @f.tool
    def get_list() -> list:
        """Return a list."""
        return [{"id": i, "name": f"item_{i}"} for i in range(100)]

    c = TestClient(f.app)
    resp = c.post("/tools/get_list", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 100
    assert resp.headers.get("content-encoding") == "gzip"


# --- enable_compression helper ---

def test_enable_compression_helper() -> None:
    """enable_compression() function works on app directly."""
    f = ApiForge(name="Helper")

    @f.tool
    def big() -> str:
        """Large response."""
        return "F" * 10000

    enable_compression(f.app, minimum_size=500)
    c = TestClient(f.app)
    resp = c.post("/tools/big", json={})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"
    assert resp.json() == "F" * 10000
