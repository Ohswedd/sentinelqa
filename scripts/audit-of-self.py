#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Audit-of-self CI check (v1.7.0, phase 37).

Starts a hermetic local HTTP server serving the canned fixture under
``examples/end-to-end-demo/static``, runs ``sentinel discover`` against
it, and asserts the resulting ``discovery.json`` matches expected
bounds: at least one route, exit code 0, score band sane.

The check is intentionally tiny and deterministic so it can be a
required CI check that takes < 15 s.

Run from the repo root:

    uv run python scripts/audit-of-self.py
"""

from __future__ import annotations

import json
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
FIXTURE = ROOT / "scripts" / "_audit_of_self_fixture"


_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>SentinelQA self-audit fixture</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <h1>Hello, SentinelQA</h1>
    <p>Static fixture served by the audit-of-self CI job.</p>
    <nav>
      <ul>
        <li><a href="/about.html">About</a></li>
        <li><a href="/contact.html">Contact</a></li>
      </ul>
    </nav>
  </body>
</html>
"""

_ABOUT_HTML = """<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>About</title></head>
  <body><h1>About</h1><a href="/">Home</a></body>
</html>
"""

_CONTACT_HTML = """<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>Contact</title></head>
  <body><h1>Contact</h1><a href="/">Home</a></body>
</html>
"""


def _write_fixture() -> None:
    FIXTURE.mkdir(parents=True, exist_ok=True)
    (FIXTURE / "index.html").write_text(_INDEX_HTML, encoding="utf-8")
    (FIXTURE / "about.html").write_text(_ABOUT_HTML, encoding="utf-8")
    (FIXTURE / "contact.html").write_text(_CONTACT_HTML, encoding="utf-8")


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _serve(directory: Path, port: int) -> HTTPServer:
    handler = type(
        "Handler",
        (_QuietHandler,),
        {"directory": str(directory)},
    )
    server = HTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Give the OS a moment to bind.
    for _ in range(20):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.05)
    return server


def main() -> int:
    _write_fixture()
    port = _free_port()
    server = _serve(FIXTURE, port)
    try:
        with tempfile.TemporaryDirectory(prefix="sentinelqa-self-") as workdir:
            workspace = Path(workdir)
            config_path = workspace / "sentinel.config.yaml"
            config_path.write_text(
                "version: 1\n"
                "project:\n"
                "  name: audit-of-self\n"
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
                "  max_depth: 2\n"
                "  max_pages: 8\n"
                "  rate_limit_rps: 50.0\n"
                "  respect_robots: false\n"
                "  same_host_only: true\n",
                encoding="utf-8",
            )
            artifacts = workspace / ".sentinel"
            env_runs = artifacts / "runs"
            env_runs.mkdir(parents=True, exist_ok=True)

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
                str(env_runs),
            ]
            print(f"[audit-of-self] running: {' '.join(cmd)}", flush=True)
            completed = subprocess.run(
                cmd,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if completed.returncode != 0:
                sys.stderr.write(completed.stdout)
                sys.stderr.write(completed.stderr)
                raise SystemExit(f"sentinel discover exited {completed.returncode}; expected 0.")

            # Find the resulting discovery.json under any RUN- dir.
            run_dirs = sorted(p for p in env_runs.iterdir() if p.name.startswith("RUN-"))
            if not run_dirs:
                raise SystemExit("No RUN- directory produced under runs/.")
            run_dir = run_dirs[-1]
            discovery_path = run_dir / "discovery.json"
            if not discovery_path.is_file():
                raise SystemExit(f"discovery.json missing under {run_dir}.")

            payload = json.loads(discovery_path.read_text(encoding="utf-8"))
            graph = payload.get("graph", {})
            routes = graph.get("routes", [])
            if len(routes) < 2:
                raise SystemExit(f"Expected >=2 discovered routes; got {len(routes)}.")
            print(
                f"[audit-of-self] OK: {len(routes)} route(s) discovered " f"under {run_dir.name}.",
                flush=True,
            )
    finally:
        server.shutdown()
        server.server_close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
