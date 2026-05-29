"""Direct coverage of `report_cmd` helper functions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinel_cli.commands.report_cmd import (
    _build_test_run,
    _load_findings,
    _load_module_results,
    _load_policy,
    _load_score_obj,
    _parse_iso,
    _ReportError,
    _rerender,
    _resolve_formats,
    _resolve_run_dir,
)


def test_resolve_run_dir_missing(tmp_path: Path) -> None:
    with pytest.raises(_ReportError):
        _resolve_run_dir(tmp_path / "runs", run_id="RUN-MISSINGAAAAA", latest=False)


def test_resolve_run_dir_dangling_latest(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    latest = runs_root / "latest"
    latest.symlink_to(runs_root / "nope")
    with pytest.raises(_ReportError):
        _resolve_run_dir(runs_root, run_id=None, latest=True)


def test_resolve_formats_empty_unknown() -> None:
    out = _resolve_formats(["bogus", " ", "also-bogus"])
    assert out == set()


def test_resolve_formats_json_alias() -> None:
    out = _resolve_formats(["JSON"])
    assert out == {"run", "findings", "score"}


def test_resolve_formats_md_alias() -> None:
    out = _resolve_formats(["md"])
    assert out == {"markdown"}


def test_resolve_formats_defaults_when_none() -> None:
    out = _resolve_formats(None)
    assert "html" in out and "junit" in out


def test_parse_iso_handles_z_suffix() -> None:
    dt = _parse_iso("2026-05-29T12:00:00Z")
    assert dt.tzinfo is not None


def test_parse_iso_invalid_raises() -> None:
    with pytest.raises(_ReportError):
        _parse_iso("not-an-iso-stamp")


def test_build_test_run_with_unknown_mode() -> None:
    run = _build_test_run(
        {
            "run_id": "RUN-MODEFALLBACK",
            "started_at": "2026-05-29T12:00:00+00:00",
            "status": "passed",
            "target": {"base_url": "https://localhost:8080", "mode": "unknown"},
        }
    )
    assert run.target.mode == "safe"


def test_load_findings_missing_returns_empty(tmp_path: Path) -> None:
    assert _load_findings(tmp_path) == []


def test_load_findings_skips_non_dict_entries(tmp_path: Path) -> None:
    (tmp_path / "findings.json").write_text(
        json.dumps(
            {
                "findings": [
                    "nope",
                    42,
                    {
                        "id": "FND-OKXAAAAAAAAA",
                        "run_id": "RUN-OKXAAAAAAAAA",
                        "module": "functional",
                        "category": "x",
                        "severity": "low",
                        "confidence": 0.5,
                        "title": "title",
                        "description": "desc",
                        "created_at": "2026-05-29T12:00:00+00:00",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    out = _load_findings(tmp_path)
    assert len(out) == 1


def test_load_score_obj_missing(tmp_path: Path) -> None:
    assert _load_score_obj(tmp_path, run_id="RUN-AAAAAAAAAAAA") is None


def test_load_score_obj_with_null_total(tmp_path: Path) -> None:
    (tmp_path / "score.json").write_text(json.dumps({"total": None}), encoding="utf-8")
    assert _load_score_obj(tmp_path, run_id="RUN-AAAAAAAAAAAA") is None


def test_load_policy_missing(tmp_path: Path) -> None:
    assert _load_policy(tmp_path, run_id="RUN-AAAAAAAAAAAA") is None


def test_load_module_results_empty(tmp_path: Path) -> None:
    assert _load_module_results(tmp_path) == []


def test_load_module_results_skips_corrupt(tmp_path: Path) -> None:
    module_dir = tmp_path / "module-results"
    module_dir.mkdir()
    (module_dir / "bad.json").write_text("not json", encoding="utf-8")
    (module_dir / "ok.json").write_text(
        json.dumps(
            {
                "name": "functional",
                "status": "passed",
                "duration_ms": 100,
                "metrics": {},
            }
        ),
        encoding="utf-8",
    )
    out = _load_module_results(tmp_path)
    assert len(out) == 1
    assert out[0].name == "functional"


def test_rerender_missing_run_json_raises(tmp_path: Path) -> None:
    with pytest.raises(_ReportError):
        _rerender(tmp_path, {"html"})
