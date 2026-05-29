"""Internal re-exports for the SDK error hierarchy.

The PUBLIC import surface lives in :mod:`sentinelqa.errors`. This module
holds the indirection so the package root can import lightweight names
without dragging the registry along on cold start (see
``sentinelqa/__init__.py``).
"""

from __future__ import annotations

from engine.errors import (
    ConfigError,
    DependencyMissingError,
    QualityGateFailedError,
    SentinelError,
    TestExecutionError,
    UnsafeTargetError,
)

__all__ = [
    "SentinelError",
    "ConfigError",
    "UnsafeTargetError",
    "DependencyMissingError",
    "TestExecutionError",
    "QualityGateFailedError",
]
