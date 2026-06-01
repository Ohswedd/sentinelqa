# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the platform install-hint catalogue."""

from __future__ import annotations

import pytest

from sentinel_cli.platform_install_hints import (
    InstallHint,
    detect_platform,
    format_hint,
    hint_for,
)


@pytest.mark.parametrize("dep", ["python", "node", "playwright", "docker", "httpx"])
@pytest.mark.parametrize("plat", ["macos", "debian", "fedora", "arch", "windows", "unknown"])
def test_every_dep_has_a_hint_on_every_platform(dep: str, plat: str) -> None:
    """The catalogue must cover every (dep, platform) pair."""

    hint = hint_for(dep, platform_id=plat)
    assert hint is not None
    assert isinstance(hint, InstallHint)
    assert hint.command, f"{dep!r} on {plat!r}: empty command"
    assert hint.docs_url.startswith("https://"), f"{dep!r} on {plat!r}: bad docs URL"


def test_unknown_dependency_returns_none() -> None:
    assert hint_for("not-a-real-dep", platform_id="macos") is None


def test_format_hint_returns_renderable_suffix() -> None:
    s = format_hint("node", platform_id="macos")
    assert s.startswith(" Install: `")
    assert "brew install node" in s
    assert "https://" in s


def test_format_hint_empty_for_unknown_dep() -> None:
    assert format_hint("not-a-real-dep") == ""


def test_macos_python_hint_uses_brew() -> None:
    hint = hint_for("python", platform_id="macos")
    assert hint is not None
    assert "brew install" in hint.command


def test_debian_node_hint_uses_nodesource() -> None:
    hint = hint_for("node", platform_id="debian")
    assert hint is not None
    assert "nodesource" in hint.command.lower()


def test_windows_hints_use_winget() -> None:
    assert "winget install" in hint_for("python", platform_id="windows").command
    assert "winget install" in hint_for("node", platform_id="windows").command
    assert "winget install" in hint_for("docker", platform_id="windows").command


def test_arch_hints_use_pacman() -> None:
    assert "pacman -S" in hint_for("python", platform_id="arch").command
    assert "pacman -S" in hint_for("node", platform_id="arch").command


def test_fedora_node_hint_uses_dnf() -> None:
    hint = hint_for("node", platform_id="fedora")
    assert hint is not None
    assert "dnf install" in hint.command


def test_detect_platform_returns_known_token() -> None:
    """``detect_platform`` must return one of the documented tokens."""

    token = detect_platform()
    assert token in {"macos", "debian", "fedora", "arch", "windows", "unknown"}


def test_format_hint_falls_back_to_unknown_when_plat_missing(monkeypatch) -> None:
    """A platform_id without an entry must use the ``unknown`` row."""

    # 'solaris' is not in any catalogue bucket.
    s = format_hint("python", platform_id="solaris")
    assert s != ""
    # The 'unknown' bucket for python uses the uv installer.
    assert "uv" in s
