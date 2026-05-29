"""Healer proposal writer (Phase 20.05).

Writes one JSON file per :class:`RepairProposal` under
``<run-dir>/healer/<suggestion-id>.json`` plus an aggregate
``<run-dir>/healer/index.json`` summary. Atomic write semantics
(write → fsync → rename) match the Phase-02 artifact writers.

The persisted shape is the :meth:`RepairProposal.to_dict` envelope
(``schema_version="1"`` per ADR-0025). Consumers (HTML report, CLI
``sentinel fix``, MCP ``suggest_fix``) read these files directly.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Sequence
from pathlib import Path

from engine.healer.models import RepairProposal

HEALER_INDEX_FILENAME = "index.json"


def _atomic_write(path: Path, data: str) -> None:
    """Write ``data`` to ``path`` atomically (temp-file + rename)."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise
    os.replace(tmp_path, path)


def write_proposal(run_dir: Path, proposal: RepairProposal) -> Path:
    """Write one proposal to ``<run-dir>/healer/<id>.json``. Returns the path."""

    healer_dir = run_dir / "healer"
    out_path = healer_dir / f"{proposal.id}.json"
    payload = json.dumps(proposal.to_dict(), indent=2, sort_keys=True)
    _atomic_write(out_path, payload + "\n")
    return out_path


def write_index(run_dir: Path, proposals: Sequence[RepairProposal]) -> Path:
    """Write the aggregate ``index.json``.

    Index shape (locked under ADR-0025):

    .. code-block:: json

        {
          "schema_version": "1",
          "count": <int>,
          "by_kind": {"locator": N, "wait": N, "fixture": N, "assertion": N},
          "proposals": [{"id": "RPR-...", "kind": "locator",
                         "confidence": 0.95, "target_test": "...",
                         "requires_human_review": false}],
        }
    """

    healer_dir = run_dir / "healer"
    sorted_proposals = sorted(proposals, key=lambda p: p.id)
    by_kind: dict[str, int] = {"locator": 0, "wait": 0, "fixture": 0, "assertion": 0}
    summary_entries: list[dict[str, object]] = []
    for proposal in sorted_proposals:
        by_kind[proposal.kind] = by_kind.get(proposal.kind, 0) + 1
        summary_entries.append(
            {
                "id": proposal.id,
                "kind": proposal.kind,
                "confidence": proposal.confidence,
                "target_test": proposal.target_test,
                "requires_human_review": proposal.requires_human_review,
            }
        )

    document = {
        "schema_version": "1",
        "count": len(sorted_proposals),
        "by_kind": by_kind,
        "proposals": summary_entries,
    }
    out_path = healer_dir / HEALER_INDEX_FILENAME
    _atomic_write(out_path, json.dumps(document, indent=2, sort_keys=True) + "\n")
    return out_path


def read_index(run_dir: Path) -> dict[str, object] | None:
    """Convenience: load ``index.json`` if present (used by the CLI)."""

    index_path = run_dir / "healer" / HEALER_INDEX_FILENAME
    if not index_path.is_file():
        return None
    document = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        return None
    return dict(document)


def read_proposal(run_dir: Path, proposal_id: str) -> dict[str, object] | None:
    """Convenience: load one persisted proposal."""

    path = run_dir / "healer" / f"{proposal_id}.json"
    if not path.is_file():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        return None
    return dict(document)


def iter_proposals(run_dir: Path) -> Iterable[dict[str, object]]:
    """Yield every persisted proposal (id-sorted) under ``run_dir``."""

    healer_dir = run_dir / "healer"
    if not healer_dir.is_dir():
        return
    for path in sorted(healer_dir.glob("RPR-*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(document, dict):
            yield dict(document)


__all__ = [
    "HEALER_INDEX_FILENAME",
    "iter_proposals",
    "read_index",
    "read_proposal",
    "write_index",
    "write_proposal",
]
