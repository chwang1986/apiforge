"""Round 35: Benchmarking utilities tests."""

import pytest
from src.testing import make_forge
from src.benchmark import (
    BenchmarkResult,
    benchmark_tool,
    run_benchmark,
    compare_tools,
    _percentile,
)


def _build():
    f = make_forge(name="Bench")

    @f.tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    @f.tool
    def heavy(x: int) -> int:
        """Heavy."""
        return x * x

    @f.tool(method="GET")
    def fast() -> str:
        """Fast."""
        return "ok"

    return f


# --- _percentile ---

def test_percentile_basic() -> None:
    vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert _percentile(vals, 50) == 5.5
    assert _percentile(vals, 0) == 1
    assert _percentile(vals, 100) == 10


def test_percentile_single() -> None:
    assert _percentile([42], 50) == 42


def test_percentile_empty() -> None:
    assert _percentile([], 50) == 0.0


# --- benchmark_tool ---

def test_benchmark_returns_result() -> None:
    f = _build()
    r = benchmark_tool(f, "add", {"a": 1, "b": 2}, iterations=20)
    assert r.iterations == 20
    assert r.errors == 0
    assert r.min_ms >= 0
    assert r.max_ms >= r.min_ms
    assert r.avg_ms >= 0
    assert r.throughput > 0
    assert r.p50_ms >= r.min_ms


def test_benchmark_percentiles_ordered() -> None:
    f = _build()
    r = benchmark_tool(f, "add", {"a": 1, "b": 2}, iterations=50)
    # p50 <= p90 <= p99
    assert r.p50_ms <= r.p90_ms + 0.1  # small tolerance for rounding
    assert r.p90_ms <= r.p99_ms + 0.1


def test_benchmark_get_tool() -> None:
    f = _build()
    r = benchmark_tool(f, "fast", iterations=20, method="GET")
    assert r.errors == 0
    assert r.throughput > 0


def test_benchmark_summary_string() -> None:
    f = _build()
    r = benchmark_tool(f, "add", {"a": 1, "b": 2}, iterations=10)
    s = r.summary()
    assert "avg=" in s
    assert "throughput=" in s
    assert "p99=" in s


def test_benchmark_all_errors_raises() -> None:
    f = _build()
    # Nonexistent tool → 404 → all errors
    with pytest.raises(RuntimeError):
        benchmark_tool(f, "nonexistent", iterations=3)


# --- run_benchmark (dict) ---

def test_run_benchmark_dict() -> None:
    f = _build()
    d = run_benchmark(f, "add", {"a": 5, "b": 5}, iterations=10)
    assert d["tool"] == "add"
    assert d["iterations"] == 10
    assert "avg_ms" in d
    assert "p99_ms" in d
    assert "throughput" in d
    assert d["summary"]


# --- compare_tools ---

def test_compare_tools_sorted() -> None:
    f = _build()
    results = compare_tools(
        f,
        {"add": {"a": 1, "b": 2}, "heavy": {"x": 3}},
        iterations=10,
    )
    assert len(results) == 2
    # Sorted by avg_ms ascending
    assert results[0]["avg_ms"] <= results[1]["avg_ms"]


# --- BenchmarkResult dataclass ---

def test_benchmark_result_dataclass() -> None:
    r = BenchmarkResult(
        iterations=10,
        min_ms=1.0,
        max_ms=10.0,
        avg_ms=5.0,
        p50_ms=4.0,
        p90_ms=8.0,
        p99_ms=9.5,
        stdev_ms=2.0,
        throughput=100.0,
        total_seconds=0.1,
    )
    assert r.iterations == 10
    assert r.errors == 0  # default
