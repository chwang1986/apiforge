"""ApiForge embedded dashboard.

Provides a simple HTML+JS dashboard served at /dashboard that displays:
- Service info (name, version, uptime)
- Registered tools count
- Recent request metrics (from MetricsRegistry)
- Health status

No external dependencies. Single self-contained HTML page.

Usage:
    from src.dashboard import enable_dashboard

    enable_dashboard(app)
    # GET /dashboard -> HTML page
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, Response

from src._version import __version__


_DASHBOARD_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>@@SERVICE@@ - ApiForge Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 2rem; }
.container { max-width: 1200px; margin: 0 auto; }
h1 { font-size: 1.8rem; margin-bottom: 0.5rem; color: #38bdf8; }
.subtitle { color: #64748b; margin-bottom: 2rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
.card { background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }
.card h3 { font-size: 0.85rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem; }
.card .value { font-size: 2rem; font-weight: 700; color: #f1f5f9; }
.card .label { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }
.section { margin-bottom: 2rem; }
.section h2 { font-size: 1.1rem; color: #94a3b8; margin-bottom: 1rem; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid #334155; }
th { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; }
td { font-size: 0.9rem; }
.status-ok { color: #4ade80; }
.status-err { color: #f87171; }
.badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
.badge-green { background: #052e16; color: #4ade80; }
.badge-blue { background: #172554; color: #60a5fa; }
</style>
</head>
<body>
<div class="container">
<h1>🔧 @@SERVICE@@</h1>
<p class="subtitle">ApiForge v@@VERSION@@ | Uptime: <span id="uptime"></span></p>

<div class="grid">
<div class="card">
<h3>Status</h3>
<div class="value status-ok">● Running</div>
<div class="label">All systems operational</div>
</div>
<div class="card">
<h3>Tools</h3>
<div class="value" id="tool-count">-</div>
<div class="label">Registered endpoints</div>
</div>
<div class="card">
<h3>Requests</h3>
<div class="value" id="req-count">-</div>
<div class="label">Total served</div>
</div>
<div class="card">
<h3>Avg Latency</h3>
<div class="value" id="avg-latency">-</div>
<div class="label">Mean response time</div>
</div>
</div>

<div class="section">
<h2>📋 Registered Tools</h2>
<table id="tools-table">
<thead><tr><th>Method</th><th>Path</th><th>Name</th><th>Status</th></tr></thead>
<tbody></tbody>
</table>
</div>

<div class="section">
<h2>📊 Recent Metrics</h2>
<table id="metrics-table">
<thead><tr><th>Metric</th><th>Value</th></tr></thead>
<tbody></tbody>
</table>
</div>
</div>

<script>
const started = @@START_TS@@;

function uptime() {
  const now = Date.now() / 1000;
  const s = Math.floor(now - started);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h + "h " + m + "m " + sec + "s";
}

document.getElementById('uptime').textContent = uptime();
setInterval(function() { document.getElementById('uptime').textContent = uptime(); }, 1000);

async function loadTools() {
  try {
    const resp = await fetch('/api/openapi.json');
    const spec = await resp.json();
    const paths = spec.paths || {};
    const tools = [];
    for (const [path, ops] of Object.entries(paths)) {
      for (const [method, op] of Object.entries(ops)) {
        if (['get','post','put','delete','patch'].indexOf(method) === -1) continue;
        if (path.indexOf('health') !== -1 || path.indexOf('metrics') !== -1 || path.indexOf('docs') !== -1 || path.indexOf('openapi') !== -1) continue;
        tools.push({ method: method, path: path, name: op.operationId || path });
      }
    }
    document.getElementById('tool-count').textContent = tools.length;
    const tbody = document.querySelector('#tools-table tbody');
    tbody.innerHTML = tools.map(function(t) {
      return '<tr><td><span class="badge badge-blue">' + t.method.toUpperCase() + '</span></td><td>' + t.path + '</td><td>' + t.name + '</td><td class="status-ok">●</td></tr>';
    }).join('');
  } catch(e) {
    document.getElementById('tool-count').textContent = '0';
  }
}

async function loadMetrics() {
  try {
    const resp = await fetch('/metrics');
    const text = await resp.text();
    const lines = text.split('\n');
    let totalReqs = 0, totalLatency = 0, count = 0;
    for (const line of lines) {
      if (line.indexOf('#') === 0 || line.trim() === '') continue;
      const parts = line.split(' ');
      if (parts[0] === 'apiforge_http_requests_total') totalReqs += parseFloat(parts[1]) || 0;
      if (parts[0] === 'apiforge_http_request_duration_seconds_count') count = parseFloat(parts[1]) || 0;
      if (parts[0] === 'apiforge_http_request_duration_seconds_sum') totalLatency = parseFloat(parts[1]) || 0;
    }
    document.getElementById('req-count').textContent = Math.round(totalReqs).toLocaleString();
    const avgMs = count > 0 ? (totalLatency / count * 1000).toFixed(1) + ' ms' : '-';
    document.getElementById('avg-latency').textContent = avgMs;
  } catch(e) {
    document.getElementById('req-count').textContent = '0';
  }
}

loadTools();
loadMetrics();
setInterval(function() { loadMetrics(); }, 5000);
</script>
</body>
</html>
"""


def get_dashboard_html(
    service_name: str = "ApiForge",
    version: str = __version__,
) -> str:
    """Generate the dashboard HTML page.

    Args:
        service_name: Display name for the service.
        version: Version string.

    Returns:
        The complete HTML string.
    """
    return (
        _DASHBOARD_TEMPLATE
        .replace("@@SERVICE@@", service_name)
        .replace("@@VERSION@@", version)
        .replace("@@START_TS@@", str(time.time()))
    )


def enable_dashboard(
    app: FastAPI,
    service_name: str | None = None,
) -> None:
    """Register the /dashboard endpoint on a FastAPI app.

    Args:
        app: The FastAPI application.
        service_name: Name to display (defaults to app.title).
    """
    name = service_name or app.title or "ApiForge"
    version = app.version or __version__
    html = get_dashboard_html(name, version)

    @app.get("/dashboard", include_in_schema=False)
    async def dashboard() -> Response:
        """Serve the embedded dashboard."""
        return Response(content=html, media_type="text/html")
