# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Persistence subsystem — sqlite-backed cross-run state.

Currently exposes :class:`FlakeDb` for the flake-rate tracker.
"""

from __future__ import annotations

from engine.persistence.flake_db import (
    DEFAULT_FLAKE_DB_PATH,
    FlakeDb,
    FlakeStat,
    Outcome,
)

__all__ = [
    "DEFAULT_FLAKE_DB_PATH",
    "FlakeDb",
    "FlakeStat",
    "Outcome",
]
