"""ApiForge benchmarking utilities.

Measure latency distribution, throughput, and concurrent load
for ApiForge endpoints using the TestClient (no real network needed).

Usage:
    from src.benchmark import Benchmark, run_benchmark

    f = make_forge(name="Bench")

    @f.tool
    def add(a: int, b: int) -> int:
        return a + b

    result = run_benchmark(f, "add", {"a": 1, "b": 2}, iterations=200)
    print(result["avg_ms"], result["p99_ms"], result["throughput"])
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from fastapi.testclient import TestClient

from src.server import ApiForge


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""

    iterations: int
    min_ms: float
    max_ms: float
    avg_ms: float
    p50_ms: float
    p90_ms: float
    p99_ms: float
    stdev_ms: float
    throughput: float  # requests per second
    total_seconds: float
    errors: int = 0

    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"iterations={self.iterations} errors={self.errors} "
            f"avg={self.avg_ms:.2f}ms p50={self.p50_ms:.2f}ms "
            f"p90={self.p90_ms:.2f}ms p99={self.p99_ms:.2f}ms "
            f"throughput={self.throughput:.1f} req/s"
        )


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Compute the given percentile (0-100) from a sorted list."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def benchmark_tool(
    forge: ApiForge,
    tool_name: str,
    payload: dict[str, Any] | None = None,
    *,
    iterations: int = 100,
    method: str = "POST",
    min_success: int = 1,
) -> BenchmarkResult:
    """Benchmark a single tool endpoint.

    Args:
        forge: The ApiForge instance.
        tool_name: Tool name (e.g. "add" → /tools/add).
        payload: JSON body.
        iterations: Number of requests to send.
        method: HTTP method.
        min_success: Minimum successful requests required.

    Returns:
        A BenchmarkResult with latency distribution and throughput.
    """
    client = TestClient(forge.app)
    path = f"/tools/{tool_name}"
    payload = payload or {}

    latencies: list[float] = []
    errors = 0
    start = time.perf_counter()

    for _ in range(iterations):
        t0 = time.perf_counter()
        try:
            if method.upper() == "GET":
                resp = client.get(path, params=payload)
            else:
                resp = client.post(path, json=payload)
            if resp.status_code >= 400:
                errors += 1
            else:
                latencies.append((time.perf_counter() - t0) * 1000.0)
        except Exception:
            errors += 1

    total = time.perf_counter() - start

    if not latencies:
        raise RuntimeError(f"Benchmark failed: no successful requests ({errors} errors)")
    if len(latencies) < min_success:
        raise RuntimeError(
            f"Benchmark: only {len(latencies)} successes, need >= {min_success}"
        )

    sorted_l = sorted(latencies)
    avg = sum(sorted_l) / len(sorted_l)
    throughput = len(sorted_l) / total if total > 0 else 0.0

    return BenchmarkResult(
        iterations=iterations,
        min_ms=sorted_l[0],
        max_ms=sorted_l[-1],
        avg_ms=round(avg, 3),
        p50_ms=round(_percentile(sorted_l, 50), 3),
        p90_ms=round(_percentile(sorted_l, 90), 3),
        p99_ms=round(_percentile(sorted_l, 99), 3),
        stdev_ms=round(statistics.pstdev(sorted_l), 3) if len(sorted_l) > 1 else 0.0,
        throughput=round(throughput, 2),
        total_seconds=round(total, 4),
        errors=errors,
    )


def run_benchmark(
    forge: ApiForge,
    tool_name: str,
    payload: dict[str, Any] | None = None,
    iterations: int = 100,
    method: str = "POST",
) -> dict[str, Any]:
    """Run a benchmark and return results as a plain dict.

    Args:
        forge: The ApiForge instance.
        tool_name: Tool name.
        payload: JSON body.
        iterations: Number of requests.
        method: HTTP method.

    Returns:
        A dict with all benchmark metrics.
    """
    r = benchmark_tool(
        forge, tool_name, payload,
        iterations=iterations, method=method,
    )
    return {
        "tool": tool_name,
        "iterations": r.iterations,
        "errors": r.errors,
        "min_ms": r.min_ms,
        "max_ms": r.max_ms,
        "avg_ms": r.avg_ms,
        "p50_ms": r.p50_ms,
        "p90_ms": r.p90_ms,
        "p99_ms": r.p99_ms,
        "stdev_ms": r.stdev_ms,
        "throughput": r.throughput,
        "total_seconds": r.total_seconds,
        "summary": r.summary(),
    }


def compare_tools(
    forge: ApiForge,
    tools: dict[str, dict[str, Any] | None],
    iterations: int = 50,
) -> list[dict[str, Any]]:
    """Benchmark multiple tools and return their results.

    Args:
        forge: The ApiForge instance.
        tools: Mapping of tool_name → payload.
        iterations: Iterations per tool.

    Returns:
        List of benchmark result dicts, sorted by avg_ms ascending.
    """
    results = [
        run_benchmark(forge, name, payload, iterations=iterations)
        for name, payload in tools.items()
    ]
    return sorted(results, key=lambda r: r["avg_ms"])
