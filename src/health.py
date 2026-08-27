"""ApiForge dependency health checks.

Provides a /health/detail endpoint that reports the status of
registered dependency checks (database, Redis, external APIs, etc).

Each check is a simple async/sync function that returns True (healthy)
or raises an exception (unhealthy).

Usage:
    forge = ApiForge(name="MyService")

    @forge.health_check("database")
    async def check_db():
        '''Check database connectivity.'''
        await db.execute("SELECT 1")

    @forge.health_check("redis")
    def check_redis():
        '''Check Redis connectivity.'''
        redis.ping()

    # GET /health/detail →
    # {
    #     "status": "ok",
    #     "checks": [
    #         {"name": "database", "status": "ok", "latency_ms": 1.2},
    #         {"name": "redis", "status": "ok", "latency_ms": 0.5}
    #     ]
    # }
"""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    name: str
    healthy: bool
    latency_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "status": "ok" if self.healthy else "fail",
            "latency_ms": round(self.latency_ms, 2),
        }
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class HealthCheck:
    """A registered health check."""

    name: str
    func: Callable
    timeout: float = 5.0

    async def run(self) -> HealthCheckResult:
        """Execute the health check with timing."""
        start = time.perf_counter()
        try:
            result = self.func()
            if inspect.isawaitable(result):
                await result
            elapsed = (time.perf_counter() - start) * 1000
            return HealthCheckResult(name=self.name, healthy=True, latency_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                name=self.name,
                healthy=False,
                latency_ms=elapsed,
                error=str(exc),
            )


class HealthRegistry:
    """Registry for health checks.

    Attributes:
        checks: List of registered HealthCheck instances.
    """

    def __init__(self) -> None:
        self.checks: list[HealthCheck] = []

    def register(
        self,
        name: str,
        func: Callable,
        timeout: float = 5.0,
    ) -> None:
        """Register a health check function."""
        self.checks.append(HealthCheck(name=name, func=func, timeout=timeout))

    def check(self, name: str) -> Callable:
        """Decorator to register a health check by name.

        Usage:
            @registry.check("database")
            async def check_db():
                ...
        """
        def decorator(func: Callable) -> Callable:
            self.register(name, func)
            return func
        return decorator

    async def run_all(self) -> list[HealthCheckResult]:
        """Run all registered health checks and collect results."""
        results = []
        for check in self.checks:
            result = await check.run()
            results.append(result)
        return results

    @property
    def all_healthy(self) -> bool:
        """Quick check: are all checks passing? (runs all checks)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        results = loop.run_until_complete(self.run_all())
        return all(r.healthy for r in results)


def install_health_checks(app: Any, registry: HealthRegistry) -> None:
    """Install a /health/detail endpoint on the FastAPI app.

    Args:
        app: The FastAPI application.
        registry: The HealthRegistry with registered checks.
    """

    @app.get("/health/detail", tags=["system"])
    async def health_detail() -> dict[str, Any]:
        """Detailed health check with per-dependency status."""
        results = await registry.run_all()
        all_healthy = all(r.healthy for r in results)
        return {
            "status": "ok" if all_healthy else "degraded",
            "checks": [r.to_dict() for r in results],
        }
