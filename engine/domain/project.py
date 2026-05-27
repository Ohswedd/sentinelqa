"""Project entity (PRD §18.1)."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field

from engine.domain.base import SentinelModel
from engine.domain.schema import CONFIG_SCHEMA_VERSION

Framework = Literal[
    "nextjs",
    "react",
    "vue",
    "svelte",
    "angular",
    "fastapi",
    "django",
    "flask",
    "express",
    "rails",
    "unknown",
]

PackageManager = Literal["pnpm", "npm", "yarn", "bun", "uv", "pip", "poetry", "unknown"]


class Project(SentinelModel):
    """The application under audit."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    name: str = Field(min_length=1, max_length=200)
    root: Path
    framework: Framework = "unknown"
    package_manager: PackageManager = "unknown"
    version: str | None = Field(default=None, max_length=64)
    schema_version: str = Field(default=CONFIG_SCHEMA_VERSION)


__all__ = ["Project", "Framework", "PackageManager"]
