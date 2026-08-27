"""Round 23: File upload tests."""

import pytest
from fastapi import File, UploadFile
from fastapi.testclient import TestClient

from src.server import ApiForge
from src._internal import is_upload_tool


# --- is_upload_tool detection ---

def test_is_upload_tool_true() -> None:
    """Function with UploadFile param is detected."""
    def upload(file: UploadFile) -> str:
        """Upload."""
        return "ok"

    assert is_upload_tool(upload) is True


def test_is_upload_tool_false() -> None:
    """Function without UploadFile is not detected."""
    def normal(a: int) -> str:
        """Normal."""
        return "ok"

    assert is_upload_tool(normal) is False


# --- Basic upload ---

def test_single_file_upload() -> None:
    """Upload a single file and get response."""
    f = ApiForge(name="Upload")

    @f.tool
    async def upload(file: UploadFile = File(...)) -> dict:
        """Upload a file."""
        content = await file.read()
        return {"filename": file.filename, "size": len(content)}

    c = TestClient(f.app)
    resp = c.post(
        "/tools/upload",
        files={"file": ("hello.txt", b"Hello World!", "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "hello.txt"
    assert data["size"] == 12


def test_upload_multiple_files() -> None:
    """Upload multiple files."""
    f = ApiForge(name="MultiUpload")

    @f.tool
    async def upload(
        file_a: UploadFile = File(...),
        file_b: UploadFile = File(...),
    ) -> dict:
        """Upload two files."""
        a = await file_a.read()
        b = await file_b.read()
        return {"a_size": len(a), "b_size": len(b)}

    c = TestClient(f.app)
    resp = c.post(
        "/tools/upload",
        files={
            "file_a": ("a.txt", b"AAA", "text/plain"),
            "file_b": ("b.txt", b"BBBB", "text/plain"),
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["a_size"] == 3
    assert data["b_size"] == 4


def test_upload_with_extra_field() -> None:
    """Upload file with additional Form field."""
    from fastapi import Form

    f = ApiForge(name="Upload+Form")

    @f.tool
    async def upload(
        file: UploadFile = File(...),
        tag: str = Form("default"),
    ) -> dict:
        """Upload with tag."""
        content = await file.read()
        return {"filename": file.filename, "size": len(content), "tag": tag}

    c = TestClient(f.app)
    resp = c.post(
        "/tools/upload",
        files={"file": ("test.png", b"\x89PNG", "image/png")},
        data={"tag": "important"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "test.png"
    assert data["tag"] == "important"


# --- Binary content preserved ---

def test_binary_content_intact() -> None:
    """Binary file content is not corrupted."""
    f = ApiForge(name="Binary")

    @f.tool
    async def upload(file: UploadFile = File(...)) -> dict:
        """Return checksum info."""
        content = await file.read()
        return {"size": len(content), "first_byte": content[0]}

    c = TestClient(f.app)
    binary_data = b"\x00\x01\x02\x03\xff\xfe"
    resp = c.post(
        "/tools/upload",
        files={"file": ("bin.dat", binary_data, "application/octet-stream")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["size"] == 6
    assert data["first_byte"] == 0


# --- Regular tools still work ---

def test_regular_tools_unaffected() -> None:
    """Normal POST tools work alongside upload tools."""
    f = ApiForge(name="Mixed")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    @f.tool
    async def upload(file: UploadFile = File(...)) -> str:
        """Upload."""
        content = await file.read()
        return f"got {len(content)} bytes"

    c = TestClient(f.app)
    # Regular tool
    resp = c.post("/tools/add", json={"a": 1, "b": 2})
    assert resp.status_code == 200
    assert resp.json() == 3

    # Upload tool
    resp = c.post("/tools/upload", files={"file": ("f.txt", b"xyz", "text/plain")})
    assert resp.status_code == 200
    assert resp.json() == "got 3 bytes"
