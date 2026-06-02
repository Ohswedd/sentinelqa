# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Self-hosted run viewer over loopback HTTP (v1.6.0).

`sentinel serve` lifts a tiny stdlib HTTP server that:

* lists past runs at ``/``,
* serves each run's ``report.html`` + ``findings.json``,
* exposes ``/api/runs.json``, ``/api/trends.json``,
  ``/api/status.json``, ``/api/diff/<a>/<b>.json``,
* hosts a tiny ``widget.js`` for embedding the status badge on a
  public status page.
"""

from __future__ import annotations

from engine.reporter.serve.app import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    ViewerApp,
    ViewerError,
    handle_request,
    render_index_html,
    serve_forever,
)

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "ViewerApp",
    "ViewerError",
    "handle_request",
    "render_index_html",
    "serve_forever",
]
