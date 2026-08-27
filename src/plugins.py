"""ApiForge plugin system.

Register plugins with lifecycle hooks that run at defined points
during request processing.

Usage:
    from src.plugins import Plugin, PluginRegistry

    def check_auth(request):
        '''Check auth header.'''
        pass

    registry = PluginRegistry()
    registry.register(Plugin(name="auth", hooks={"before_request": check_auth}))
    results = registry.execute("before_request", request=req)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


HOOK_POINTS = [
    "startup",
    "shutdown",
    "before_request",
    "after_request",
    "before_tool",
    "after_tool",
    "on_error",
]


@dataclass
class Plugin:
    """A registered plugin.

    Args:
        name: Unique plugin name.
        func: The plugin's main function (optional).
        hooks: Mapping of hook point names to callables.
        enabled: Whether the plugin is active.
        metadata: Arbitrary plugin metadata.
    """

    name: str
    func: Callable | None = None
    hooks: dict[str, Callable] = field(default_factory=dict)
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Check for configuration issues. Returns list of warnings."""
        warnings: list[str] = []
        if not self.name:
            warnings.append("Plugin has no name")
        for hook_name, handler in self.hooks.items():
            if hook_name not in HOOK_POINTS:
                warnings.append(f"Unknown hook point: {hook_name}")
            if not callable(handler):
                warnings.append(f"Hook {hook_name} is not callable")
        return warnings


class PluginRegistry:
    """Manages a collection of plugins and their hook execution.

    Usage:
        registry = PluginRegistry()
        registry.register(Plugin(name="auth", hooks={"before_request": check_auth}))
        registry.execute_all("before_request", request=context)
    """

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        # Maps hook_point -> list of (plugin, handler) tuples
        self._hooks: dict[str, list[tuple[Plugin, Callable]]] = {h: [] for h in HOOK_POINTS}

    def register(self, plugin: Plugin) -> None:
        """Register a plugin and wire its hooks.

        Args:
            plugin: The Plugin instance to register.

        Raises:
            ValueError: If a plugin with the same name is already registered.
        """
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin already registered: {plugin.name}")
        self._plugins[plugin.name] = plugin
        for hook_point, handler in plugin.hooks.items():
            if hook_point in self._hooks:
                self._hooks[hook_point].append((plugin, handler))

    def unregister(self, name: str) -> None:
        """Remove a plugin and its hooks.

        Args:
            name: Plugin name to remove.

        Raises:
            KeyError: If plugin not found.
        """
        plugin = self._plugins.pop(name)
        for hook_point in self._hooks:
            self._hooks[hook_point] = [
                (p, h) for p, h in self._hooks[hook_point] if p.name != name
            ]

    def execute(self, hook_point: str, **kwargs: Any) -> list[Any]:
        """Execute all handlers for a hook point in registration order.

        Only enabled plugins are executed.

        Args:
            hook_point: One of HOOK_POINTS.
            **kwargs: Passed to each handler.

        Returns:
            List of return values from each handler.
        """
        if hook_point not in self._hooks:
            raise ValueError(f"Unknown hook point: {hook_point}")
        results = []
        for plugin, handler in self._hooks[hook_point]:
            if plugin.enabled:
                results.append(handler(**kwargs))
        return results

    def execute_all(self, hook_point: str, **kwargs: Any) -> list[Any]:
        """Alias for execute()."""
        return self.execute(hook_point, **kwargs)

    def get_plugin(self, name: str) -> Plugin:
        """Get a registered plugin by name."""
        return self._plugins[name]

    def list_plugins(self) -> list[str]:
        """List all registered plugin names."""
        return list(self._plugins.keys())

    def enabled_plugins(self) -> list[Plugin]:
        """List enabled plugins only."""
        return [p for p in self._plugins.values() if p.enabled]

    def disable(self, name: str) -> None:
        """Disable a plugin (its hooks won't execute)."""
        self._plugins[name].enabled = False

    def enable(self, name: str) -> None:
        """Re-enable a plugin."""
        self._plugins[name].enabled = True

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        return name in self._plugins


def create_registry() -> PluginRegistry:
    """Create a new PluginRegistry (convenience factory)."""
    return PluginRegistry()


def define_plugin(
    name: str,
    hooks: dict[str, Callable] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable:
    """Decorator to define a plugin function.

    Usage:
        @define_plugin("auth", hooks={"before_request": check_auth})
        def auth_plugin():
            '''Handle auth.'''
            pass
    """

    def decorator(func: Callable) -> Plugin:
        return Plugin(
            name=name,
            func=func,
            hooks=hooks or {},
            metadata=metadata or {},
        )

    return decorator
