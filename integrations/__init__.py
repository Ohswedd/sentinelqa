"""SentinelQA integrations (Phase 25).

Each subpackage adapts SentinelQA to an external service (remote
browser runner, chat webhook, issue tracker). CLAUDE.md §7 / §35:
the engine MUST NOT import these directly — it depends only on the
SDK plugin Protocols (:mod:`sentinelqa.plugins`) or invokes them via
CLI entry points. Credentials are read from environment variables at
call time, never logged, never written to disk (CLAUDE.md §33).
"""

from __future__ import annotations
