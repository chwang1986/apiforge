"""Round 38: Hot reload server tests."""

import os
import time
import tempfile
import threading
import pytest

from src.hotreload import (
    FileWatcher,
    HotReloadServer,
    ReloadEvent,
    should_reload,
    reload_app,
)
from src.server import ApiForge


# --- ReloadEvent ---

def test_reload_event_fields() -> None:
    e = ReloadEvent(path="/a.py", mtime_before=1.0, mtime_after=2.0)
    assert e.path == "/a.py"
    assert e.mtime_before == 1.0
    assert e.mtime_after == 2.0
    assert e.timestamp > 0
    assert "a.py" in e.description()


# --- should_reload ---

def test_should_reload_normal_py() -> None:
    e = ReloadEvent(path="/src/main.py", mtime_before=1, mtime_after=2)
    assert should_reload(e) is True


def test_should_reload_pyc_ignored() -> None:
    e = ReloadEvent(path="/src/__pycache__/main.cpython-311.pyc", mtime_before=1, mtime_after=2)
    assert should_reload(e) is False


def test_should_reload_pytest_cache_ignored() -> None:
    e = ReloadEvent(path="/.pytest_cache/v/cache", mtime_before=1, mtime_after=2)
    assert should_reload(e) is False


# --- FileWatcher ---

def test_watcher_detects_change() -> None:
    """Watcher detects file modification."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create a file
        filepath = os.path.join(tmp, "test.py")
        with open(filepath, "w") as f:
            f.write("x = 1\n")

        events: list[ReloadEvent] = []
        watcher = FileWatcher(paths=[tmp], poll_interval=0.05)
        watcher.set_callback(lambda e: events.append(e))
        watcher.start()

        # Wait for initial scan
        time.sleep(0.1)

        # Modify the file (force mtime change)
        time.sleep(0.05)
        with open(filepath, "w") as f:
            f.write("x = 2\n")
        os.utime(filepath, (time.time() + 1, time.time() + 1))

        # Wait for detection
        time.sleep(0.2)
        watcher.stop()

        assert len(events) >= 1
        assert any("test.py" in e.path for e in events)


def test_watcher_no_false_positive() -> None:
    """No change → no events."""
    with tempfile.TemporaryDirectory() as tmp:
        filepath = os.path.join(tmp, "stable.py")
        with open(filepath, "w") as f:
            f.write("x = 1\n")

        events: list[ReloadEvent] = []
        watcher = FileWatcher(paths=[tmp], poll_interval=0.05)
        watcher.set_callback(lambda e: events.append(e))
        watcher.start()
        time.sleep(0.3)
        watcher.stop()

        assert len(events) == 0


def test_watcher_scans_directories() -> None:
    """Watcher scans .py files in directories."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = os.path.join(tmp, "src")
        os.makedirs(sub)
        with open(os.path.join(sub, "mod.py"), "w") as f:
            f.write("x = 1\n")

        watcher = FileWatcher(paths=[tmp], poll_interval=0.5)
        mtimes = watcher._scan()
        assert any("mod.py" in p for p in mtimes)


# --- reload_app ---

def test_reload_app_returns_fresh_instance() -> None:
    """reload_app creates a new app."""
    call_count = 0

    def factory() -> ApiForge:
        nonlocal call_count
        call_count += 1
        f = ApiForge(name=f"Reloading{call_count}")
        return f

    f1 = reload_app(factory)
    f2 = reload_app(factory)
    assert f1.name == "Reloading1"
    assert f2.name == "Reloading2"
    assert f1 is not f2


# --- HotReloadServer ---

def test_hotreload_server_create_app() -> None:
    """create_app returns a fresh FastAPI app."""
    f = ApiForge(name="HotReload")

    @f.tool
    def ping() -> str:
        """Ping."""
        return "pong"

    server = HotReloadServer(
        app_factory=lambda: f.app,
        watch_paths=["."],
    )
    app = server.create_app()
    assert app is f.app
    # Verify it has routes
    assert len(app.routes) > 0


def test_hotreload_server_init_defaults() -> None:
    """Default watch_paths is ['.']."""
    server = HotReloadServer(app_factory=lambda: ApiForge(name="X").app)
    assert server.watch_paths == ["."]
    assert server.poll_interval == 1.0
