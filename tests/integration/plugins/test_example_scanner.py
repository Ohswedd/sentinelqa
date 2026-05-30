"""Phase 24 task 24.06 — reference scanner example test."""

from __future__ import annotations

# Add the example to sys.path so the import works even without
# `pip install -e`.
import sys
from pathlib import Path

import pytest
from engine.plugins import build_plugin_context, load_from_entry_point

EXAMPLE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "examples"
    / "plugins"
    / "sentinelqa-scanner-example"
    / "src"
)
sys.path.insert(0, str(EXAMPLE_ROOT))

from sentinelqa_scanner_example.plugin import HeaderChecker  # type: ignore[import-not-found]  # noqa: E402, I001


def _ctx(tmp_path: Path, *, granted: frozenset[str]) -> object:
    return build_plugin_context(
        plugin_name="header-checker",
        run_id="RUN-AAAAAAAAAAAA",
        target_url="http://localhost",
        run_dir=tmp_path,
        config_snapshot={},
        granted_permissions=granted,
    )


def test_header_checker_emits_finding_when_header_missing(tmp_path: Path) -> None:
    plugin = HeaderChecker()
    result = plugin.run(_ctx(tmp_path, granted=frozenset()))

    # _fetch returns {} by default → header missing → one finding.
    assert result.status == "failed"
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.module == "header-checker"
    assert finding.severity == "low"
    assert "X-Frame-Options" in finding.title


def test_header_checker_passes_when_header_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = HeaderChecker()
    monkeypatch.setattr(plugin, "_fetch", lambda url, *, context: {"X-Frame-Options": "DENY"})
    result = plugin.run(_ctx(tmp_path, granted=frozenset()))
    assert result.status == "passed"
    assert result.findings == ()


def test_header_checker_passes_isinstance_scanner_protocol() -> None:
    from sentinelqa.plugins import ScannerPlugin

    assert isinstance(HeaderChecker(), ScannerPlugin)


def test_header_checker_manifest_synthesises_correctly() -> None:
    # Synthesise the manifest the same way the loader does.
    from engine.plugins.manifest import load_manifest_dict
    from engine.plugins.registry import _synthesise_manifest_from_object

    manifest = load_manifest_dict(_synthesise_manifest_from_object(HeaderChecker()))

    assert manifest.kind == "scanner"
    assert manifest.name == "header-checker"
    assert "network.outbound" in manifest.permissions
    assert "fs.write:.sentinel/runs" in manifest.permissions
    assert manifest.requires_protocol == ">=1.0,<2.0"


def test_header_checker_loads_from_synthetic_entry_point(make_entry_point) -> None:
    ep = make_entry_point(
        "header-checker",
        "tests.fakes.header_checker_entry:HeaderChecker",
        HeaderChecker,
    )
    loaded = load_from_entry_point(ep)
    assert loaded.manifest.name == "header-checker"
    assert loaded.manifest.kind == "scanner"
