"""Unit tests for :mod:`modules.visual.findings`."""

from __future__ import annotations

from pathlib import Path

from engine.domain.ids import IdGenerator

from modules.visual.findings import findings_from_diffs
from modules.visual.models import DiffOutcome


def _outcome(status: str, **overrides: object) -> DiffOutcome:
    base = dict(
        route_slug="home",
        viewport="mobile",
        status=status,
        diff_fraction=0.1,
        differing_pixels=50,
        total_pixels=500,
        ssim=0.9,
        threshold=0.02,
        min_similarity=0.95,
        baseline_path=Path("/tmp/baseline.png"),
        current_path=Path("/tmp/current.png"),
        diff_path=Path("/tmp/diff.png"),
        width=10,
        height=50,
    )
    base.update(overrides)
    return DiffOutcome(**base)  # type: ignore[arg-type]


def test_findings_emits_for_differ(tmp_path: Path) -> None:
    findings = findings_from_diffs(
        [_outcome("differ")],
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
        run_dir=tmp_path,
    )
    assert len(findings) == 1
    finding = findings[0]
    assert finding.category == "visual_pixel_diff"
    assert finding.severity == "medium"
    assert finding.module == "visual"
    assert finding.location.route == "home"
    assert finding.affected_target == "http://localhost"
    assert finding.recommendation
    assert finding.description.startswith("Visual diff exceeded threshold")
    assert "SSIM=" in finding.description


def test_findings_skip_match_and_missing_baseline(tmp_path: Path) -> None:
    outcomes = [_outcome("match"), _outcome("missing_baseline")]
    findings = findings_from_diffs(
        outcomes,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
        run_dir=tmp_path,
    )
    assert findings == ()


def test_size_mismatch_severity_is_high(tmp_path: Path) -> None:
    findings = findings_from_diffs(
        [_outcome("size_mismatch")],
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
        run_dir=tmp_path,
    )
    assert findings[0].severity == "high"
    assert findings[0].category == "visual_size_mismatch"


def test_missing_current_marked_medium_and_titled(tmp_path: Path) -> None:
    findings = findings_from_diffs(
        [_outcome("missing_current", diff_path=None)],
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
        run_dir=tmp_path,
    )
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].title.startswith("Visual capture missing")


def test_evidence_paths_relativise_to_run_dir(tmp_path: Path) -> None:
    inside = tmp_path / "visual" / "baseline.png"
    inside.parent.mkdir(parents=True, exist_ok=True)
    inside.write_bytes(b"")
    findings = findings_from_diffs(
        [_outcome("differ", baseline_path=inside, current_path=None, diff_path=None)],
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
        run_dir=tmp_path,
    )
    assert findings[0].evidence
    paths = tuple(str(e.path) for e in findings[0].evidence)
    assert "visual/baseline.png" in paths


def test_evidence_fallback_when_all_paths_none(tmp_path: Path) -> None:
    findings = findings_from_diffs(
        [
            _outcome(
                "differ",
                baseline_path=None,
                current_path=None,
                diff_path=None,
            )
        ],
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
        run_dir=tmp_path,
    )
    paths = tuple(str(e.path) for e in findings[0].evidence)
    assert paths == ("visual/index.json",)


def test_unexpected_status_silently_skipped(tmp_path: Path) -> None:
    findings = findings_from_diffs(
        [_outcome("bogus")],
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
        run_dir=tmp_path,
    )
    assert findings == ()
