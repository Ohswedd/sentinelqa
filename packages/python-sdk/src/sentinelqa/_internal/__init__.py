"""Internal SDK helpers — NOT public API (our engineering rules, our product spec).

Anything in this package may change without notice between minor
versions. The single-underscore prefix is a hard rule per :
external code that imports from ``sentinelqa._internal`` is taking on
its own breakage risk.
"""

from __future__ import annotations

__all__: list[str] = []
