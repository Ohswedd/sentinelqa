"""Phase 20.05 — Writer + index unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.domain.evidence import Evidence
from engine.domain.ids import IdGenerator
from engine.healer.models import LocatorDescriptor, RepairProposal
from engine.healer.writer import (
    HEALER_INDEX_FILENAME,
    iter_proposals,
    read_index,
    read_proposal,
    write_index,
    write_proposal,
)


def _make_proposal(gen: IdGenerator, *, kind: str = "locator") -> RepairProposal:
    return RepairProposal(
        id=gen.new("RPR"),
        kind=kind,  # type: ignore[arg-type]
        target_test="tests/sentinel/login.spec.ts",
        target_test_line=5,
        original_behavior="await page.getByRole('button', { name: /sign in/i });",
        proposed_change="await page.getByRole('button', { name: /log in/i });",
        confidence=0.95,
        reason="Button renamed from 'Sign in' to 'Log in'.",
        evidence=(
            Evidence(
                id=gen.new("EVD"),
                type="source_ref",
                path=Path("tests/sentinel/login.spec.ts"),
            ),
        ),
        requires_human_review=False,
        unified_diff="--- a\n+++ b\n@@ -1,1 +1,1 @@\n-old\n+new\n",
        descriptor=LocatorDescriptor(role="button", accessible_name="Log in"),
    )


def test_write_proposal_round_trip(tmp_path: Path) -> None:
    gen = IdGenerator()
    proposal = _make_proposal(gen)
    out_path = write_proposal(tmp_path, proposal)
    assert out_path.is_file()
    assert out_path.parent == tmp_path / "healer"
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded["id"] == proposal.id
    assert loaded["kind"] == "locator"
    assert loaded["schema_version"] == "1"


def test_read_proposal_returns_dict_or_none(tmp_path: Path) -> None:
    gen = IdGenerator()
    proposal = _make_proposal(gen)
    write_proposal(tmp_path, proposal)
    fetched = read_proposal(tmp_path, proposal.id)
    assert fetched is not None
    assert fetched["id"] == proposal.id
    assert read_proposal(tmp_path, "RPR-MISSINGMISSI") is None


def test_index_summarizes_proposals_by_kind(tmp_path: Path) -> None:
    gen = IdGenerator()
    a = _make_proposal(gen, kind="locator")
    b = _make_proposal(gen, kind="wait")
    c = _make_proposal(gen, kind="locator")
    write_proposal(tmp_path, a)
    write_proposal(tmp_path, b)
    write_proposal(tmp_path, c)
    write_index(tmp_path, [a, b, c])

    doc = read_index(tmp_path)
    assert doc is not None
    assert doc["count"] == 3
    by_kind = doc["by_kind"]
    assert isinstance(by_kind, dict)
    assert by_kind["locator"] == 2
    assert by_kind["wait"] == 1
    assert by_kind["fixture"] == 0
    assert by_kind["assertion"] == 0
    proposals = doc["proposals"]
    assert isinstance(proposals, list)
    # Sorted by id.
    ids = [p["id"] for p in proposals]
    assert ids == sorted(ids)


def test_iter_proposals_yields_all(tmp_path: Path) -> None:
    gen = IdGenerator()
    a = _make_proposal(gen)
    b = _make_proposal(gen)
    write_proposal(tmp_path, a)
    write_proposal(tmp_path, b)
    docs = list(iter_proposals(tmp_path))
    assert len(docs) == 2
    ids: list[str] = sorted(str(doc["id"]) for doc in docs)
    assert ids == sorted([a.id, b.id])


def test_iter_proposals_empty_when_no_dir(tmp_path: Path) -> None:
    assert list(iter_proposals(tmp_path)) == []


def test_read_index_returns_none_when_absent(tmp_path: Path) -> None:
    assert read_index(tmp_path) is None


def test_atomic_write_replaces_existing_file(tmp_path: Path) -> None:
    gen = IdGenerator()
    proposal = _make_proposal(gen)
    write_proposal(tmp_path, proposal)
    new = proposal.model_copy(update={"reason": "Different reason now."})
    write_proposal(tmp_path, new)
    loaded = read_proposal(tmp_path, proposal.id)
    assert loaded is not None
    assert loaded["reason"] == "Different reason now."


def test_proposal_with_invalid_unified_diff_header_is_rejected() -> None:
    with pytest.raises(ValueError, match="unified_diff must begin with"):
        RepairProposal(
            id="RPR-AAAAAAAAAAAA",
            kind="locator",
            target_test="t.spec.ts",
            original_behavior="x",
            proposed_change="y",
            confidence=1.0,
            reason="r",
            evidence=(),
            requires_human_review=False,
            unified_diff="not a diff",
        )


def test_proposal_id_rejects_wrong_prefix() -> None:
    with pytest.raises(ValueError):
        RepairProposal(
            id="FND-AAAAAAAAAAAA",
            kind="locator",
            target_test="t.spec.ts",
            original_behavior="x",
            proposed_change="y",
            confidence=1.0,
            reason="r",
            evidence=(),
            requires_human_review=False,
            unified_diff="--- a\n+++ b\n@@\n-x\n+y\n",
        )


def test_index_filename_constant() -> None:
    assert HEALER_INDEX_FILENAME == "index.json"


def test_read_index_returns_none_for_non_dict(tmp_path: Path) -> None:
    (tmp_path / "healer").mkdir()
    (tmp_path / "healer" / HEALER_INDEX_FILENAME).write_text("[]", encoding="utf-8")
    assert read_index(tmp_path) is None


def test_read_proposal_returns_none_for_non_dict(tmp_path: Path) -> None:
    (tmp_path / "healer").mkdir()
    (tmp_path / "healer" / "RPR-AAAAAAAAAAAA.json").write_text("[]", encoding="utf-8")
    assert read_proposal(tmp_path, "RPR-AAAAAAAAAAAA") is None


def test_iter_proposals_skips_non_dict_documents(tmp_path: Path) -> None:
    (tmp_path / "healer").mkdir()
    (tmp_path / "healer" / "RPR-AAAAAAAAAAAA.json").write_text("[]", encoding="utf-8")
    docs = list(iter_proposals(tmp_path))
    assert docs == []


def test_atomic_write_cleans_up_tmp_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If `os.replace` fails, the .tmp sidecar must be removed."""

    import os

    gen = IdGenerator()
    proposal = _make_proposal(gen)
    healer_dir = tmp_path / "healer"
    healer_dir.mkdir()

    real_fsync = os.fsync

    def boom(_fd: int) -> None:
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(os, "fsync", boom)
    with pytest.raises(OSError):
        write_proposal(tmp_path, proposal)
    monkeypatch.setattr(os, "fsync", real_fsync)
    # The tmp sidecar should NOT remain.
    tmp_sidecars = list(healer_dir.glob("*.tmp"))
    assert tmp_sidecars == []
