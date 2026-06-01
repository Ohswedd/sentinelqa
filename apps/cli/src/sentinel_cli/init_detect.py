"""Framework / package-manager detection for `sentinel init`.

All functions return ``None`` when uncertain — guessing produces silent
config drift, which CLAUDE §12 forbids.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from engine.domain.project import Framework, PackageManager

# A defensive cap so a malicious or accidentally-huge file (e.g. a giant
# pyproject.toml with embedded data) never gets fully read into memory.
_MAX_READ_BYTES: Final[int] = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Detection:
    framework: Framework
    package_manager: PackageManager
    has_playwright: bool
    project_name: str | None
    base_url: str | None


def _read_text_safe(path: Path) -> str | None:
    try:
        if not path.exists() or not path.is_file():
            return None
        size = path.stat().st_size
        if size > _MAX_READ_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def detect_framework(root: Path) -> Framework:
    """Best-effort framework guess.

    Returns ``"unknown"`` when nothing matches. This stays in the
    `Framework` literal so ProjectConfig validation cannot fail on a
    write-and-reload cycle.
    """

    for pattern in ("next.config.js", "next.config.ts", "next.config.mjs", "next.config.cjs"):
        if (root / pattern).exists():
            return "nextjs"
    # Vite projects are most commonly React under the hood; pick "react"
    # rather than guessing the rendering framework wrong.
    for pattern in ("vite.config.js", "vite.config.ts"):
        if (root / pattern).exists():
            return "react"

    pkg = _read_text_safe(root / "package.json")
    if pkg is not None:
        try:
            data = json.loads(pkg)
        except ValueError:
            data = {}
        deps = {
            **(data.get("dependencies") or {}),
            **(data.get("devDependencies") or {}),
        }
        if "next" in deps:
            return "nextjs"
        if "express" in deps:
            return "express"
        if "@angular/core" in deps:
            return "angular"
        if "svelte" in deps:
            return "svelte"
        if "vue" in deps:
            return "vue"
        if "react" in deps:
            return "react"

    pyproj = _read_text_safe(root / "pyproject.toml")
    if pyproj is not None:
        if re.search(r"\bfastapi\b", pyproj, re.IGNORECASE):
            return "fastapi"
        if re.search(r"\bdjango\b", pyproj, re.IGNORECASE):
            return "django"
        if re.search(r"\bflask\b", pyproj, re.IGNORECASE):
            return "flask"

    requirements = _read_text_safe(root / "requirements.txt")
    if requirements is not None:
        lowered = requirements.lower()
        if "fastapi" in lowered:
            return "fastapi"
        if "django" in lowered:
            return "django"
        if "flask" in lowered:
            return "flask"

    return "unknown"


def detect_package_manager(root: Path) -> PackageManager:
    """Detect the JS or Python package manager from lockfiles."""

    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "package-lock.json").exists():
        return "npm"
    if (root / "uv.lock").exists():
        return "uv"
    if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists():
        return "pip"
    return "unknown"


def detect_playwright(root: Path) -> bool:
    """Return True if `@playwright/test` appears in package.json deps."""

    pkg = _read_text_safe(root / "package.json")
    if pkg is None:
        return False
    try:
        data = json.loads(pkg)
    except ValueError:
        return False
    for section in ("dependencies", "devDependencies"):
        if "@playwright/test" in (data.get(section) or {}):
            return True
    return False


def detect_project_name(root: Path) -> str | None:
    pkg = _read_text_safe(root / "package.json")
    if pkg is not None:
        try:
            data = json.loads(pkg)
            name = data.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        except ValueError:
            pass

    pyproj = _read_text_safe(root / "pyproject.toml")
    if pyproj is not None:
        match = re.search(r'^\s*name\s*=\s*"([^"]+)"', pyproj, re.MULTILINE)
        if match:
            return match.group(1)

    # Fall back to the parent directory name for an absolute-anchored read.
    try:
        resolved = root.resolve()
        if resolved.name:
            return resolved.name
    except OSError:
        return None
    return None


def detect(root: Path) -> Detection:
    """Run every detector and return a frozen :class:`Detection`."""

    return Detection(
        framework=detect_framework(root),
        package_manager=detect_package_manager(root),
        has_playwright=detect_playwright(root),
        project_name=detect_project_name(root),
        base_url=None,
    )


# `dump_config` is passed in as a callable so this module does not have
# to import the loader directly (keeps the dependency explicit and lets
# tests substitute a stub).
def render_config(
    *,
    project_root: Path,
    detection: Detection,
    dump_config: Callable[..., str],
) -> str:
    """Compose the YAML string for a freshly-initialized project."""

    from engine.config.schema import (
        ProjectConfig,
        RootConfig,
        TargetConfig,
    )

    project_name = detection.project_name or project_root.resolve().name or "sentinelqa-project"
    framework: Framework = detection.framework
    pkg_mgr: PackageManager = detection.package_manager

    root_config = RootConfig(
        project=ProjectConfig(
            name=project_name,
            framework=framework,
            package_manager=pkg_mgr,
        ),
        target=TargetConfig(
            base_url="http://localhost:3000",  # type: ignore[arg-type]
            allowed_hosts=("localhost", "127.0.0.1"),
        ),
    )

    yaml_body = dump_config(root_config)
    header = (
        "# SentinelQA configuration — generated by `sentinel init`.\n"
        "# Edit `target.base_url` to point at your app and add additional\n"
        "# `allowed_hosts` only for hosts you own or are authorized to test.\n"
        "# Secrets must come from environment variables, never inline.\n"
    )
    return header + yaml_body


__all__ = [
    "Detection",
    "Framework",
    "PackageManager",
    "detect",
    "detect_framework",
    "detect_package_manager",
    "detect_playwright",
    "detect_project_name",
    "render_config",
]
