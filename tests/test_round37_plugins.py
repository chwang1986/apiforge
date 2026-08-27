"""Round 37: Plugin system tests."""

import pytest
from src.plugins import (
    Plugin,
    PluginRegistry,
    create_registry,
    define_plugin,
    HOOK_POINTS,
)


def _make_registry_with_plugins() -> PluginRegistry:
    """Create a registry with two plugins that have before_request hooks."""
    calls: list[str] = []

    def hook_a(ctx):
        calls.append("a")
        return "a_result"

    def hook_b(ctx):
        calls.append("b")
        return "b_result"

    registry = create_registry()
    registry.register(Plugin(name="plugin_a", hooks={"before_request": hook_a}))
    registry.register(Plugin(name="plugin_b", hooks={"before_request": hook_b}))
    return registry


# --- Basic registration ---

def test_register_and_list() -> None:
    r = _make_registry_with_plugins()
    assert len(r) == 2
    assert "plugin_a" in r
    assert "plugin_b" in r
    assert set(r.list_plugins()) == {"plugin_a", "plugin_b"}


def test_duplicate_register_raises() -> None:
    r = create_registry()
    r.register(Plugin(name="x", hooks={}))
    with pytest.raises(ValueError, match="already registered"):
        r.register(Plugin(name="x", hooks={}))


# --- Hook execution ---

def test_execute_before_request() -> None:
    r = _make_registry_with_plugins()
    results = r.execute("before_request", ctx={"request": "GET /"})
    assert results == ["a_result", "b_result"]


def test_execute_unknown_hook_raises() -> None:
    r = create_registry()
    with pytest.raises(ValueError, match="Unknown hook"):
        r.execute("nonexistent_hook")


# --- Enable/Disable ---

def test_disable_plugin_skips_hooks() -> None:
    r = _make_registry_with_plugins()
    r.disable("plugin_a")
    results = r.execute("before_request", ctx={})
    assert results == ["b_result"]  # only plugin_b ran


def test_enable_plugin_restores() -> None:
    r = _make_registry_with_plugins()
    r.disable("plugin_a")
    r.enable("plugin_a")
    results = r.execute("before_request", ctx={})
    assert results == ["a_result", "b_result"]


def test_enabled_plugins_list() -> None:
    r = _make_registry_with_plugins()
    r.disable("plugin_a")
    enabled = r.enabled_plugins()
    assert len(enabled) == 1
    assert enabled[0].name == "plugin_b"


# --- Unregister ---

def test_unregister_removes_hooks() -> None:
    r = _make_registry_with_plugins()
    r.unregister("plugin_a")
    assert "plugin_a" not in r
    results = r.execute("before_request", ctx={})
    assert results == ["b_result"]


def test_unregister_missing_raises() -> None:
    r = create_registry()
    with pytest.raises(KeyError):
        r.unregister("nonexistent")


# --- Plugin dataclass ---

def test_plugin_validate_ok() -> None:
    p = Plugin(name="ok", hooks={"before_request": lambda x: None})
    assert p.validate() == []


def test_plugin_validate_warnings() -> None:
    p = Plugin(name="bad", hooks={"unknown_hook": lambda x: None})
    warnings = p.validate()
    assert any("Unknown hook" in w for w in warnings)


# --- HOOK_POINTS ---

def test_hook_points_constant() -> None:
    assert "before_request" in HOOK_POINTS
    assert "after_request" in HOOK_POINTS
    assert "startup" in HOOK_POINTS
    assert len(HOOK_POINTS) == 7


# --- define_plugin decorator ---

def test_define_plugin() -> None:
    def my_handler(ctx):
        return "done"

    @define_plugin("test-plugin", hooks={"before_request": my_handler})
    def my_plugin():
        """My plugin."""
        pass

    assert isinstance(my_plugin, Plugin)
    assert my_plugin.name == "test-plugin"
    assert "before_request" in my_plugin.hooks


# --- Multiple hook points ---

def test_multiple_hook_points() -> None:
    def before(ctx):
        return "before"

    def after(ctx):
        return "after"

    r = create_registry()
    r.register(Plugin(name="multi", hooks={
        "before_request": before,
        "after_request": after,
    }))
    assert r.execute("before_request", ctx={}) == ["before"]
    assert r.execute("after_request", ctx={}) == ["after"]
