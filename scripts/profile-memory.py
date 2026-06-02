#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Memory profile harness (v1.8.0, phase 38).

Spawns ``sentinel discover`` against a synthetic ``N``-route fixture
and reports the subprocess's peak resident set size (RSS). Use this
to spot regressions before a release: the goal stated in
``plans/IMPROVEMENTS.md`` §10 is to drive a 200-route audit comfortably
under 2 GB.

The harness is intentionally stdlib-only (no ``memray``, no
``psutil``) so it runs in CI without an extra dependency. RSS is
sampled via ``resource.getrusage(RUSAGE_CHILDREN)`` after the
subprocess has exited — accurate, exit-time-only, no polling overhead.

Run from the repo root:

    uv run python scripts/profile-memory.py
    uv run python scripts/profile-memory.py --routes 200 --json /tmp/m.json
"""

from __future__ import annotations

import argparse
import json
import resource
import socket
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import closing
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _route_html(idx: int, total: int) -> str:
    next_idx = (idx + 1) % total
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        f"<title>Route {idx}</title></head><body>"
        f"<h1>Route {idx}</h1>"
        f'<a href="/route-{next_idx}.html">next</a> '
        '<a href="/">home</a>'
        "</body></html>\n"
    )


def _write_fixture(directory: Path, routes: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.html").write_text(_route_html(0, routes), encoding="utf-8")
    for i in range(routes):
        (directory / f"route-{i}.html").write_text(_route_html(i, routes), encoding="utf-8")


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _serve(directory: Path, port: int) -> HTTPServer:
    handler = type("Handler", (_QuietHandler,), {"directory": str(directory)})
    server = HTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for _ in range(50):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.02)
    return server


def _ru_maxrss_kb(after: resource.struct_rusage, before: resource.struct_rusage) -> int:
    """Return the additional peak RSS this run added, in kilobytes.

    On Linux ``ru_maxrss`` is reported in kilobytes; on macOS / Darwin
    it is in bytes (Mavericks onward, per Apple's ``getrusage(2)``).
    """

    delta = after.ru_maxrss - before.ru_maxrss
    if sys.platform == "darwin":
        return delta // 1024
    return delta


def _profile_run(routes: int, work_root: Path) -> dict[str, object]:
    fixture_dir = work_root / "fixture"
    _write_fixture(fixture_dir, routes)
    port = _free_port()
    server = _serve(fixture_dir, port)
    workspace = work_root / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    config_path = workspace / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: profile-memory\n"
        "  framework: nextjs\n"
        "  package_manager: pnpm\n"
        f"target:\n"
        f"  base_url: http://127.0.0.1:{port}\n"
        "  allowed_hosts:\n"
        "    - 127.0.0.1\n"
        "modules:\n"
        "  functional: false\n"
        "  api: false\n"
        "  accessibility: false\n"
        "  performance: false\n"
        "  visual: false\n"
        "  security: false\n"
        "  llm_audit: false\n"
        "discovery:\n"
        '  engine: "http"\n'
        f"  max_depth: 3\n"
        f"  max_pages: {routes + 8}\n"
        "  rate_limit_rps: 80.0\n"
        "  respect_robots: false\n"
        "  same_host_only: true\n",
        encoding="utf-8",
    )
    runs_dir = workspace / ".sentinel" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "uv",
        "run",
        "sentinel",
        "--config",
        str(config_path),
        "discover",
        "--url",
        f"http://127.0.0.1:{port}",
        "--output",
        str(runs_dir),
    ]
    try:
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.perf_counter()
        completed = subprocess.run(cmd, capture_output=True, check=False, timeout=300)
        elapsed = time.perf_counter() - start
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
    finally:
        server.shutdown()
        server.server_close()

    peak_kb = _ru_maxrss_kb(after, before)
    return {
        "routes": routes,
        "exit_code": completed.returncode,
        "wall_clock_s": round(elapsed, 3),
        "peak_rss_kb": peak_kb,
        "peak_rss_mb": round(peak_kb / 1024, 2),
        "stderr_tail": completed.stderr.decode("utf-8", errors="replace")[-500:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Memory profile a discover run.")
    parser.add_argument("--routes", type=int, default=20, help="Routes in the fixture.")
    parser.add_argument("--json", type=Path, default=None, help="Write JSON output here.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="sentinelqa-memprof-") as workdir:
        payload = _profile_run(args.routes, Path(workdir))

    if payload["exit_code"] != 0:
        sys.stderr.write(f"discover exited {payload['exit_code']}\n")
        sys.stderr.write(payload["stderr_tail"])  # type: ignore[arg-type]
        return 2

    rendered = json.dumps(
        {k: v for k, v in payload.items() if k != "stderr_tail"},
        indent=2,
        sort_keys=True,
    )
    print(rendered)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
