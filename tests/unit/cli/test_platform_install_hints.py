# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the platform install-hint catalogue."""

from __future__ import annotations

from pathlib import Path

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
    for dep in ("python", "node", "docker"):
        hint = hint_for(dep, platform_id="windows")
        assert hint is not None
        assert "winget install" in hint.command


def test_arch_hints_use_pacman() -> None:
    for dep in ("python", "node"):
        hint = hint_for(dep, platform_id="arch")
        assert hint is not None
        assert "pacman -S" in hint.command


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


def test_detect_platform_reports_macos_on_darwin(monkeypatch) -> None:
    import platform as _platform

    monkeypatch.setattr(_platform, "system", lambda: "Darwin")
    assert detect_platform() == "macos"


def test_detect_platform_reports_windows(monkeypatch) -> None:
    import platform as _platform

    monkeypatch.setattr(_platform, "system", lambda: "Windows")
    assert detect_platform() == "windows"


def test_detect_platform_reports_unknown_for_obscure_kernel(monkeypatch) -> None:
    import platform as _platform

    monkeypatch.setattr(_platform, "system", lambda: "Haiku")
    assert detect_platform() == "unknown"


def _patch_os_release(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: str | None) -> None:
    import platform as _platform

    from sentinel_cli import platform_install_hints as mod

    monkeypatch.setattr(_platform, "system", lambda: "Linux")
    osr: Path = tmp_path / "os-release"
    if body is not None:
        osr.write_text(body, encoding="utf-8")

    def _proxy(arg: str) -> Path:
        if arg == "/etc/os-release":
            return osr if body is not None else tmp_path / "definitely-not-here"
        return Path(arg)

    monkeypatch.setattr(mod, "Path", _proxy)


def test_detect_linux_family_resolves_debian(monkeypatch, tmp_path) -> None:
    _patch_os_release(monkeypatch, tmp_path, 'ID=ubuntu\nID_LIKE="debian"\n')
    assert detect_platform() == "debian"


def test_detect_linux_family_resolves_fedora(monkeypatch, tmp_path) -> None:
    _patch_os_release(monkeypatch, tmp_path, 'ID=fedora\nVERSION_ID="41"\n')
    assert detect_platform() == "fedora"


def test_detect_linux_family_resolves_arch(monkeypatch, tmp_path) -> None:
    _patch_os_release(monkeypatch, tmp_path, "ID=arch\n")
    assert detect_platform() == "arch"


def test_detect_linux_family_returns_unknown_when_missing(monkeypatch, tmp_path) -> None:
    _patch_os_release(monkeypatch, tmp_path, body=None)
    assert detect_platform() == "unknown"


def test_detect_linux_family_returns_unknown_for_unknown_id(monkeypatch, tmp_path) -> None:
    _patch_os_release(monkeypatch, tmp_path, "ID=plan9\n")
    assert detect_platform() == "unknown"
