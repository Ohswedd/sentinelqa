"""SentinelQA integrations.

Each subpackage adapts SentinelQA to an external service (remote
browser runner, chat webhook, issue tracker). our engineering rules / §35:
the engine MUST NOT import these directly — it depends only on the
SDK plugin Protocols (:mod:`sentinelqa.plugins`) or invokes them via
CLI entry points. Credentials are read from environment variables at
call time, never logged, never written to disk.
"""

from __future__ import annotations
