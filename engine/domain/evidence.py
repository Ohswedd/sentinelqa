"""Evidence entity."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import field_validator

from engine.domain.base import SentinelModel
from engine.domain.ids import validate_id
from engine.domain.schema import FINDINGS_SCHEMA_VERSION

EvidenceType = Literal[
    "screenshot",
    "video",
    "trace",
    "har",
    "console_log",
    "network_log",
    "dom_snapshot",
    "stack_trace",
    "api_sample",
    "source_ref",
]


class Evidence(SentinelModel):
    """One artifact proving a finding."""

    SCHEMA_VERSION: ClassVar[str] = FINDINGS_SCHEMA_VERSION

    id: str
    type: EvidenceType
    path: Path
    redacted: bool = True

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="EVD")


__all__ = ["Evidence", "EvidenceType"]
