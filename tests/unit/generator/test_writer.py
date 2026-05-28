"""Tests for the generator file writer (task 07.06 — overwrite guard)."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.generator.render import GENERATOR_BANNER
from engine.generator.writer import (
    OverwriteError,
    WriteOutcome,
    is_sentinel_managed,
    write_generated_files,
)


def test_writes_new_files(tmp_path: Path) -> None:
    out = tmp_path / "out" / "a.ts"
    outcomes = write_generated_files([(out, GENERATOR_BANNER + "// body\n")])
    assert outcomes == [WriteOutcome(path=out, status="written")]
    assert out.read_text(encoding="utf-8").startswith("// SentinelQA Generated")


def test_unchanged_when_identical_managed_file(tmp_path: Path) -> None:
    out = tmp_path / "a.ts"
    body = GENERATOR_BANNER + "// hello\n"
    write_generated_files([(out, body)])
    second = write_generated_files([(out, body)])
    assert second[0].status == "unchanged"


def test_updates_managed_file_when_content_differs(tmp_path: Path) -> None:
    out = tmp_path / "a.ts"
    write_generated_files([(out, GENERATOR_BANNER + "// v1\n")])
    second = write_generated_files([(out, GENERATOR_BANNER + "// v2\n")])
    assert second[0].status == "updated"
    assert out.read_text(encoding="utf-8").endswith("// v2\n")


def test_refuses_to_overwrite_hand_owned_file(tmp_path: Path) -> None:
    out = tmp_path / "a.ts"
    out.write_text("// user wrote this\n", encoding="utf-8")
    with pytest.raises(OverwriteError) as exc:
        write_generated_files([(out, GENERATOR_BANNER + "// generated\n")])
    assert exc.value.path == out
    assert out.read_text(encoding="utf-8") == "// user wrote this\n"


def test_force_overwrites_hand_owned(tmp_path: Path) -> None:
    out = tmp_path / "a.ts"
    out.write_text("// hand\n", encoding="utf-8")
    outcomes = write_generated_files(
        [(out, GENERATOR_BANNER + "// generated\n")],
        force=True,
    )
    assert outcomes[0].status == "written"
    assert "// generated" in out.read_text(encoding="utf-8")


def test_is_sentinel_managed_only_inspects_head(tmp_path: Path) -> None:
    out = tmp_path / "a.ts"
    out.write_text(
        "// hand\n" + " " * 10_000 + "// SentinelQA Generated — do not edit by hand\n",
        encoding="utf-8",
    )
    # Marker is past the 4 KiB head window → considered hand-owned.
    assert is_sentinel_managed(out) is False


def test_is_sentinel_managed_handles_missing_file(tmp_path: Path) -> None:
    assert is_sentinel_managed(tmp_path / "nope.ts") is False
