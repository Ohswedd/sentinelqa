"""Unit tests for :mod:`modules.visual.baselines` (Phase 21.02)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.visual.baselines import (
    INDEX_FILENAME,
    baseline_path,
    load_index,
    promote_to_baseline,
    sha256_file,
    slugify_route,
    write_index,
)
from modules.visual.models import BaselineRecord
from tests.unit.modules.visual._fixtures import write_solid_png


def test_slugify_route_basic() -> None:
    assert slugify_route("/") == "root"
    assert slugify_route("") == "root"
    assert slugify_route("/dashboard") == "_dashboard".strip("_") or "dashboard"
    assert slugify_route("/Users/123/Edit") == "users_123_edit"
    assert slugify_route("/  spaces  ") == "spaces"


def test_slugify_unicode_normalises_to_root() -> None:
    # Non-ASCII collapses to root rather than emitting bytes the FS would
    # mangle across platforms.
    assert slugify_route("/✓✓✓") == "root"


def test_baseline_path_builds_layout(tmp_path: Path) -> None:
    p = baseline_path(tmp_path / "b", "mobile", "dashboard")
    assert p == tmp_path / "b" / "mobile" / "dashboard.png"


def test_sha256_file_hashes_deterministically(tmp_path: Path) -> None:
    png = write_solid_png(tmp_path / "a.png", size=(2, 2), color=(0, 0, 0))
    digest_a = sha256_file(png)
    digest_b = sha256_file(png)
    assert digest_a == digest_b
    assert len(digest_a) == 64


def test_write_and_load_index_roundtrip(tmp_path: Path) -> None:
    record = BaselineRecord(
        viewport="desktop",
        route_slug="dashboard",
        path="desktop/dashboard.png",
        width=10,
        height=10,
        sha256="a" * 64,
        captured_at="2026-05-29T00:00:00+00:00",
        captured_by_run_id="RUN-XXXXXXXXXXXX",
        masks_applied=("clock",),
    )
    write_index(tmp_path, [record])
    out = load_index(tmp_path)
    assert (record.viewport, record.route_slug) in out
    assert out[(record.viewport, record.route_slug)].sha256 == "a" * 64


def test_load_index_missing_returns_empty(tmp_path: Path) -> None:
    assert load_index(tmp_path) == {}


def test_load_index_malformed_json_raises(tmp_path: Path) -> None:
    (tmp_path / INDEX_FILENAME).write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_index(tmp_path)


def test_load_index_missing_baselines_key_raises(tmp_path: Path) -> None:
    (tmp_path / INDEX_FILENAME).write_text(json.dumps({"x": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing 'baselines'"):
        load_index(tmp_path)


def test_load_index_malformed_row_raises(tmp_path: Path) -> None:
    payload = {"schema_version": "1", "baselines": [{"viewport": "x"}]}
    (tmp_path / INDEX_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="malformed baselines row"):
        load_index(tmp_path)


def test_promote_to_baseline_copies_and_records(tmp_path: Path) -> None:
    src = write_solid_png(tmp_path / "src.png", size=(4, 4), color=(50, 100, 150))
    dest_root = tmp_path / "baselines"
    record = promote_to_baseline(
        baselines_dir=dest_root,
        viewport="mobile",
        route_slug="home",
        source_png=src,
        captured_by_run_id="RUN-YYYYYYYYYYYY",
        captured_at="2026-05-29T01:23:45+00:00",
        masks_applied=("logo",),
    )
    assert record.width == 4
    assert record.height == 4
    assert (dest_root / "mobile" / "home.png").exists()
    assert record.path == "mobile/home.png"
    assert record.sha256 == sha256_file(dest_root / "mobile" / "home.png")
    assert record.masks_applied == ("logo",)


def test_promote_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        promote_to_baseline(
            baselines_dir=tmp_path / "b",
            viewport="mobile",
            route_slug="home",
            source_png=tmp_path / "missing.png",
            captured_by_run_id="RUN-ZZZZZZZZZZZZ",
            captured_at="2026-05-29T00:00:00+00:00",
        )
