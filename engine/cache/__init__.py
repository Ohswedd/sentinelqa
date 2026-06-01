# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Disk-backed cache primitives used by the run lifecycle.

The cache underpins three v1.2.0 features — discovery cache, plan cache,
and incremental audits — by providing a small, content-addressed
key-value store keyed on a deterministic fingerprint of the project's
source tree.

Public surface:

- :class:`SourceFingerprint` — content hash of the project's source.
- :func:`compute_fingerprint` — build a fingerprint from a directory.
- :class:`CacheStore` — namespaced byte store under ``.sentinel/cache/``.
"""

from __future__ import annotations

from engine.cache.fingerprint import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_INCLUDE_SUFFIXES,
    SourceFingerprint,
    compute_fingerprint,
)
from engine.cache.store import CacheStore

__all__ = [
    "DEFAULT_EXCLUDE_DIRS",
    "DEFAULT_INCLUDE_SUFFIXES",
    "CacheStore",
    "SourceFingerprint",
    "compute_fingerprint",
]
