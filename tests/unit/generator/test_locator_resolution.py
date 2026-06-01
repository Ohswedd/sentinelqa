"""Tests for the ``_resolve_sentinel_ts`` binary discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.generator import locator_strategy
from engine.generator.locator_strategy import LocatorAuditError


def test_resolve_uses_path_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        locator_strategy,
        "which",
        lambda name: "/usr/bin/sentinel-ts" if name == "sentinel-ts" else None,
    )
    assert locator_strategy._resolve_sentinel_ts() == "/usr/bin/sentinel-ts"


def test_resolve_falls_back_to_workspace_when_path_misses(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    cli_js = repo_root / "packages" / "ts-runtime" / "dist" / "cli.js"
    cli_js.parent.mkdir(parents=True)
    cli_js.write_text("// fake\n", encoding="utf-8")

    def fake_which(name: str) -> str | None:
        if name == "sentinel-ts":
            return None
        if name == "node":
            return "/usr/local/bin/node"
        return None

    monkeypatch.setattr(locator_strategy, "which", fake_which)
    # Patch the module's __file__ so parents[2] yields our tmp_path.
    fake_pkg = repo_root / "engine" / "generator" / "locator_strategy.py"
    fake_pkg.parent.mkdir(parents=True)
    fake_pkg.write_text("# fake\n", encoding="utf-8")
    monkeypatch.setattr(locator_strategy, "__file__", str(fake_pkg))

    resolved = locator_strategy._resolve_sentinel_ts()
    assert resolved.startswith("NODE::/usr/local/bin/node::")
    assert resolved.endswith("cli.js")


def test_resolve_workspace_missing_node_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    cli_js = repo_root / "packages" / "ts-runtime" / "dist" / "cli.js"
    cli_js.parent.mkdir(parents=True)
    cli_js.write_text("// fake\n", encoding="utf-8")

    monkeypatch.setattr(locator_strategy, "which", lambda _name: None)
    fake_pkg = repo_root / "engine" / "generator" / "locator_strategy.py"
    fake_pkg.parent.mkdir(parents=True)
    fake_pkg.write_text("# fake\n", encoding="utf-8")
    monkeypatch.setattr(locator_strategy, "__file__", str(fake_pkg))

    with pytest.raises(LocatorAuditError):
        locator_strategy._resolve_sentinel_ts()


def test_resolve_missing_everywhere_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(locator_strategy, "which", lambda _name: None)
    # Force a __file__ where the workspace fallback also fails.
    fake_pkg = tmp_path / "engine" / "generator" / "locator_strategy.py"
    fake_pkg.parent.mkdir(parents=True)
    fake_pkg.write_text("# fake\n", encoding="utf-8")
    monkeypatch.setattr(locator_strategy, "__file__", str(fake_pkg))

    with pytest.raises(LocatorAuditError) as exc:
        locator_strategy._resolve_sentinel_ts()
    assert "not found" in str(exc.value).lower()


def test_build_command_for_workspace_node(tmp_path: Path) -> None:
    file = tmp_path / "spec.ts"
    file.write_text("x", encoding="utf-8")
    cmd = locator_strategy._build_command(
        "NODE::/usr/local/bin/node::/tmp/ts/dist/cli.js",
        [file],
        tmp_path,
    )
    assert cmd[:2] == ["/usr/local/bin/node", "/tmp/ts/dist/cli.js"]
    assert "audit-locators" in cmd
    assert "--file" in cmd


def test_build_command_uses_relative_path_under_cwd(tmp_path: Path) -> None:
    file = tmp_path / "sub" / "spec.ts"
    file.parent.mkdir()
    file.write_text("x", encoding="utf-8")
    cmd = locator_strategy._build_command("/bin/sentinel-ts", [file], tmp_path)
    # Relative path used (so the audit reports tidy file paths).
    assert "sub/spec.ts" in cmd
