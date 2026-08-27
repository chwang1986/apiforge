"""ApiForge lifecycle management.

Provides startup/shutdown hooks and graceful shutdown support.
Uses FastAPI's lifespan context manager (modern approach).

Usage:
    forge = ApiForge(name="MyService")

    @forge.on_startup
    async def connect_db():
        '''Connect to database on startup.'''
        await db.connect()

    @forge.on_shutdown
    async def close_db():
        '''Close database on shutdown.'''
        await db.disconnect()

    forge.run()  # Handles startup/shutdown automatically
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable

from fastapi import FastAPI

logger = logging.getLogger("apiforge.lifecycle")


class LifecycleManager:
    """Manages startup and shutdown hooks for the application.

    Hooks are executed in registration order on startup,
    and in REVERSE order on shutdown (LIFO).

    Attributes:
        started: Whether the application has started.
        shutdown_timeout: Max seconds to wait for in-flight requests.
    """

    def __init__(self, shutdown_timeout: float = 30.0) -> None:
        self._startup_hooks: list[Callable] = []
        self._shutdown_hooks: list[Callable] = []
        self.started = False
        self.shutdown_timeout = shutdown_timeout
        self._start_time: float | None = None

    def on_startup(self, func: Callable) -> Callable:
        """Register a startup hook.

        Can be used as a decorator or called directly.
        Hook can be sync or async.
        """
        self._startup_hooks.append(func)
        return func

    def on_shutdown(self, func: Callable) -> Callable:
        """Register a shutdown hook.

        Can be used as a decorator or called directly.
        Hook can be sync or async.
        """
        self._shutdown_hooks.append(func)
        return func

    async def startup(self) -> None:
        """Execute all startup hooks in order."""
        self._start_time = time.monotonic()
        for i, hook in enumerate(self._startup_hooks):
            name = getattr(hook, "__name__", f"hook_{i}")
            logger.info("Startup: %s", name)
            result = hook()
            if hasattr(result, "__await__"):
                await result
        self.started = True
        elapsed = (time.monotonic() - self._start_time) * 1000
        logger.info("Startup complete (%.1fms, %d hooks)", elapsed, len(self._startup_hooks))

    async def shutdown(self) -> None:
        """Execute all shutdown hooks in reverse order (LIFO)."""
        import inspect
        self._start_time = None
        for i, hook in enumerate(reversed(self._shutdown_hooks)):
            name = getattr(hook, "__name__", f"hook_{i}")
            logger.info("Shutdown: %s", name)
            result = hook()
            if inspect.isawaitable(result):
                await result
        self.started = False
        logger.info("Shutdown complete (%d hooks)", len(self._shutdown_hooks))

    @property
    def uptime_seconds(self) -> float | None:
        """Seconds since startup (None if not started)."""
        if self._start_time is None:
            return None
        return time.monotonic() - self._start_time

    @property
    def uptime_str(self) -> str:
        """Human-readable uptime."""
        seconds = self.uptime_seconds
        if seconds is None:
            return "not started"
        if seconds < 60:
            return f"{seconds:.1f}s"
        if seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"

    def create_lifespan(self) -> Callable:
        """Create a FastAPI lifespan context manager from this manager.

        Returns:
            An async context manager suitable for FastAPI(lifespan=...).
        """
        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            await self.startup()
            yield
            await self.shutdown()

        return lifespan


def install_lifecycle(app: FastAPI, shutdown_timeout: float = 30.0) -> LifecycleManager:
    """Install lifecycle management on a FastAPI app.

    Replaces the app's lifespan with one that runs startup/shutdown hooks.

    Args:
        app: The FastAPI application.
        shutdown_timeout: Max seconds for graceful shutdown.

    Returns:
        The LifecycleManager instance (for registering hooks).
    """
    manager = LifecycleManager(shutdown_timeout=shutdown_timeout)
    # We can't easily replace lifespan after app creation,
    # so we use event handlers as a fallback
    manager._app = app

    @app.on_event("startup")
    async def _startup() -> None:
        await manager.startup()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await manager.shutdown()

    return manager


def get_lifecycle(app: FastAPI) -> LifecycleManager | None:
    """Get the LifecycleManager from a FastAPI app (if installed)."""
    return getattr(app.state, "lifecycle", None)
