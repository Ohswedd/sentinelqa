"""``run-config.json`` shape passed from Python to ``sentinel-ts run``.

This Pydantic model mirrors the ``RunConfigSchema`` defined in
``packages/ts-runtime/src/runner.ts`` (Phase 04). Both halves of the
bridge MUST stay in sync — the parity is exercised by
``tests/integration/runner/test_run_config_parity.py``.

The TS side accepts an additive set of optional fields; Python emits
exactly what the runner needs (no `extra="ignore"` so we catch drift).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PROTOCOL_VERSION = "1.0.0"


class ShardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    current: int = Field(ge=1)
    total: int = Field(ge=1)


class RunConfig(BaseModel):
    """The JSON blob ``sentinel-ts run --input <path>`` reads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PROTOCOL_VERSION
    run_id: str = Field(min_length=1)
    target: str = Field(min_length=1)
    run_dir: str = Field(min_length=1)
    spec_files: tuple[str, ...] = Field(default_factory=tuple)
    workers: int | None = Field(default=None, ge=1, le=64)
    shard: ShardConfig | None = None
    browser: Literal["chromium", "firefox", "webkit"] = "chromium"
    headless: bool = True
    timeout_ms: int = Field(default=30_000, ge=1_000, le=600_000)
    retries: int = Field(default=0, ge=0, le=10)
    env: dict[str, str] = Field(default_factory=dict)


__all__ = ["PROTOCOL_VERSION", "RunConfig", "ShardConfig"]
