# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Platform-specific install hints for the ``sentinel doctor`` command.

When ``doctor`` reports a missing or out-of-date dependency, it appends
a copy-pasteable install command tailored to the user's OS so they
don't have to web-search "how to install Node on Ubuntu".

The hints intentionally cover the most common managers (Homebrew on
macOS, apt on Debian/Ubuntu, dnf on Fedora/RHEL, pacman on Arch,
winget on Windows) plus a generic fallback. We do **not** try to
detect every distro — a single best guess + a "see also" URL beats
a wrong specific command.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class InstallHint:
    """A single OS-tailored install command plus a documentation link."""

    command: str
    docs_url: str


# --------------------------------------------------------------------------- #
# OS detection
# --------------------------------------------------------------------------- #


def detect_platform() -> str:
    """Return one of ``macos`` / ``debian`` / ``fedora`` / ``arch`` / ``windows`` / ``unknown``.

    The detection prefers `/etc/os-release` on Linux so distro family
    names are exact instead of guessed from the kernel string.
    """

    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return _detect_linux_family()
    return "unknown"


def _detect_linux_family() -> str:
    osr = Path("/etc/os-release")
    if not osr.is_file():
        return "unknown"
    try:
        text = osr.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "unknown"
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        fields[k.strip()] = v.strip().strip('"').strip("'")
    id_like = (fields.get("ID_LIKE") or "").lower()
    distro_id = (fields.get("ID") or "").lower()
    combined = f"{distro_id} {id_like}".strip()
    if any(t in combined for t in ("debian", "ubuntu")):
        return "debian"
    if any(t in combined for t in ("fedora", "rhel", "centos")):
        return "fedora"
    if any(t in combined for t in ("arch", "manjaro")):
        return "arch"
    return "unknown"


# --------------------------------------------------------------------------- #
# Hint catalogue
# --------------------------------------------------------------------------- #

# Each entry maps a (dependency, platform) tuple to an InstallHint.
# The keys are stable; adding a platform never requires touching callers.

_PYTHON_HINTS: dict[str, InstallHint] = {
    "macos": InstallHint(
        command="brew install python@3.12 uv",
        docs_url="https://docs.astral.sh/uv/getting-started/installation/",
    ),
    "debian": InstallHint(
        command="curl -LsSf https://astral.sh/uv/install.sh | sh && uv python install 3.12",
        docs_url="https://docs.astral.sh/uv/getting-started/installation/",
    ),
    "fedora": InstallHint(
        command="curl -LsSf https://astral.sh/uv/install.sh | sh && uv python install 3.12",
        docs_url="https://docs.astral.sh/uv/getting-started/installation/",
    ),
    "arch": InstallHint(
        command="sudo pacman -S python uv",
        docs_url="https://docs.astral.sh/uv/getting-started/installation/",
    ),
    "windows": InstallHint(
        command="winget install --id Python.Python.3.12 -e && winget install --id astral-sh.uv -e",
        docs_url="https://docs.astral.sh/uv/getting-started/installation/",
    ),
    "unknown": InstallHint(
        command="curl -LsSf https://astral.sh/uv/install.sh | sh && uv python install 3.12",
        docs_url="https://docs.astral.sh/uv/getting-started/installation/",
    ),
}

_NODE_HINTS: dict[str, InstallHint] = {
    "macos": InstallHint(
        command="brew install node@20 && brew link --force node@20",
        docs_url="https://nodejs.org/en/download",
    ),
    "debian": InstallHint(
        command=(
            "curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - "
            "&& sudo apt-get install -y nodejs"
        ),
        docs_url="https://github.com/nodesource/distributions",
    ),
    "fedora": InstallHint(
        command="sudo dnf install -y nodejs npm",
        docs_url="https://nodejs.org/en/download/package-manager",
    ),
    "arch": InstallHint(
        command="sudo pacman -S nodejs npm",
        docs_url="https://wiki.archlinux.org/title/Node.js",
    ),
    "windows": InstallHint(
        command="winget install --id OpenJS.NodeJS.LTS -e",
        docs_url="https://nodejs.org/en/download",
    ),
    "unknown": InstallHint(
        command="See https://nodejs.org/en/download to install Node 20+.",
        docs_url="https://nodejs.org/en/download",
    ),
}

_PLAYWRIGHT_HINTS: dict[str, InstallHint] = {
    plat: InstallHint(
        command="npx playwright install --with-deps",
        docs_url="https://playwright.dev/docs/intro",
    )
    for plat in ("macos", "debian", "fedora", "arch", "windows", "unknown")
}

_DOCKER_HINTS: dict[str, InstallHint] = {
    "macos": InstallHint(
        command="brew install --cask docker",
        docs_url="https://docs.docker.com/desktop/setup/install/mac-install/",
    ),
    "debian": InstallHint(
        command="curl -fsSL https://get.docker.com | sh",
        docs_url="https://docs.docker.com/engine/install/",
    ),
    "fedora": InstallHint(
        command="sudo dnf install -y docker && sudo systemctl enable --now docker",
        docs_url="https://docs.docker.com/engine/install/fedora/",
    ),
    "arch": InstallHint(
        command="sudo pacman -S docker && sudo systemctl enable --now docker",
        docs_url="https://wiki.archlinux.org/title/Docker",
    ),
    "windows": InstallHint(
        command="winget install --id Docker.DockerDesktop -e",
        docs_url="https://docs.docker.com/desktop/setup/install/windows-install/",
    ),
    "unknown": InstallHint(
        command="See https://docs.docker.com/engine/install/",
        docs_url="https://docs.docker.com/engine/install/",
    ),
}

_HTTPX_HINTS: dict[str, InstallHint] = {
    plat: InstallHint(
        command="pip install httpx",
        docs_url="https://www.python-httpx.org/",
    )
    for plat in ("macos", "debian", "fedora", "arch", "windows", "unknown")
}


_CATALOGUE: dict[str, dict[str, InstallHint]] = {
    "python": _PYTHON_HINTS,
    "node": _NODE_HINTS,
    "playwright": _PLAYWRIGHT_HINTS,
    "docker": _DOCKER_HINTS,
    "httpx": _HTTPX_HINTS,
}


def hint_for(dependency: str, *, platform_id: str | None = None) -> InstallHint | None:
    """Return the install hint for ``dependency`` on the current platform.

    ``platform_id`` lets tests pin the platform without touching
    ``platform.system()``. ``None`` ↦ resolve via :func:`detect_platform`.
    Returns ``None`` if the dependency has no registered hint.
    """

    bucket = _CATALOGUE.get(dependency)
    if bucket is None:
        return None
    plat = platform_id or detect_platform()
    return bucket.get(plat) or bucket.get("unknown")


def format_hint(dependency: str, *, platform_id: str | None = None) -> str:
    """Render a one-line suffix to append to a ``DoctorCheck.suggestion``.

    Returns an empty string when no hint exists so the caller can
    append it unconditionally:

    >>> check.suggestion += format_hint("node")
    """

    hint = hint_for(dependency, platform_id=platform_id)
    if hint is None:
        return ""
    return f" Install: `{hint.command}` (docs: {hint.docs_url})"


__all__ = [
    "InstallHint",
    "detect_platform",
    "format_hint",
    "hint_for",
]
