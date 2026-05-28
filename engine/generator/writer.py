"""Generator file writer (task 07.06).

Writes generated TypeScript files to disk while respecting hand-edits.
A file is considered SentinelQA-managed only if it contains
:data:`GENERATOR_BANNER_MARKER` near the top; otherwise the writer
treats it as hand-owned and refuses to clobber it unless ``--force``
is set.

Writes are atomic (write to a temp file then rename) so a crash mid-run
never leaves a half-written spec on disk.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from engine.generator.render import GENERATOR_BANNER_MARKER


class OverwriteError(RuntimeError):
    """Raised when ``write_generated_files`` refuses to overwrite a hand-owned file."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            f"{path}: file exists and does not carry the SentinelQA banner; "
            "re-run with --force to overwrite, or remove the file."
        )
        self.path = path


@dataclass(frozen=True)
class WriteOutcome:
    """Per-file outcome of a write attempt."""

    path: Path
    status: str
    """One of: ``written`` (new file), ``updated`` (overwrote managed file),
    ``unchanged`` (identical content), ``preserved`` (hand-owned, skipped)."""


def is_sentinel_managed(path: Path) -> bool:
    """Return ``True`` when ``path`` contains the SentinelQA banner marker."""

    if not path.exists():
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    # Check only the first 4 KiB so we never scan large files.
    return GENERATOR_BANNER_MARKER in head[:4096]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".sentinel-gen-", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def write_generated_files(
    files: Sequence[tuple[Path, str]],
    *,
    force: bool = False,
) -> list[WriteOutcome]:
    """Write each ``(path, content)`` pair atomically; respect hand-edits.

    Behavior:

    - New path → write, return ``written``.
    - Existing managed path (has banner) with same content → return ``unchanged``.
    - Existing managed path with different content → overwrite, return ``updated``.
    - Existing hand-owned path → raise :class:`OverwriteError` unless ``force`` is True.
    """

    outcomes: list[WriteOutcome] = []
    for path, content in files:
        if path.exists():
            managed = is_sentinel_managed(path)
            if not managed and not force:
                raise OverwriteError(path)
            existing = path.read_text(encoding="utf-8", errors="replace")
            if managed and existing == content:
                outcomes.append(WriteOutcome(path=path, status="unchanged"))
                continue
            _atomic_write(path, content)
            outcomes.append(WriteOutcome(path=path, status="updated" if managed else "written"))
            continue
        _atomic_write(path, content)
        outcomes.append(WriteOutcome(path=path, status="written"))
    return outcomes


__all__ = ["OverwriteError", "WriteOutcome", "is_sentinel_managed", "write_generated_files"]
