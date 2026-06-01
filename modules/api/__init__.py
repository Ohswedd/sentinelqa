"""Safe API testing module (Phase 22, the documentation, ADR-0020).

Importing this package wires :class:`ApiModule` into the default
orchestrator registry so ``sentinel api`` and ``sentinel audit`` both
pick it up automatically.

Capabilities (the documentation, our engineering rules):

- OpenAPI contract validation (per-endpoint schema check).
- GraphQL contract validation (SDL operation probe).
- Negative cases (bounded variant generation).
- Auth-matrix probing (anonymous / expired / cross-user).
- API latency budget evaluation (dedup'd with the Phase 12 perf module).
- Pagination boundary + uniform error-shape detection.
- Backward-compatibility diff against the previous snapshot.

No aggressive fuzzing path exists in this module. The body-size cap in
:func:`modules.api.http_client.safe_request` enforces a hard 64 KB
ceiling regardless of config. The
``tests/security/test_api_no_aggressive_flags.py`` guard greps the
package + the CLI surface to keep forbidden literals out.
"""

from __future__ import annotations

from modules.api.module import (
    ApiIssue,
    ApiModule,
    ApiModuleOptions,
    register_with_default_registry,
)

register_with_default_registry()


__all__ = [
    "ApiIssue",
    "ApiModule",
    "ApiModuleOptions",
    "register_with_default_registry",
]
