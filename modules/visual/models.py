"""Typed models the visual module uses internally."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Storage layout
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BaselineRecord:
    """One row of ``baselines/index.json``."""

    viewport: str
    route_slug: str
    path: str  # POSIX path under baselines_dir
    width: int
    height: int
    sha256: str
    captured_at: str  # ISO8601
    captured_by_run_id: str
    masks_applied: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Diff outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiffOutcome:
    """Result of comparing one (route, viewport) pair.

    ``status`` is one of:

    - ``match`` — baseline exists; diff fraction below the threshold
    (and SSIM above ``min_similarity`` when perceptual is enabled).
    - ``differ`` — baseline exists; threshold exceeded.
    - ``missing_baseline`` — current captured but no baseline on disk.
    - ``missing_current`` — baseline exists but no current capture.
    - ``size_mismatch`` — images differ in size (treated as differ
    with a dedicated category for the report).
    """

    route_slug: str
    viewport: str
    status: str  # 'match' | 'differ' | 'missing_baseline' | 'missing_current' | 'size_mismatch'
    diff_fraction: float = 0.0
    differing_pixels: int = 0
    total_pixels: int = 0
    ssim: float | None = None
    threshold: float = 0.0
    min_similarity: float | None = None
    baseline_path: Path | None = None
    current_path: Path | None = None
    diff_path: Path | None = None
    masks_applied: tuple[str, ...] = field(default_factory=tuple)
    width: int = 0
    height: int = 0

    @property
    def is_finding(self) -> bool:
        return self.status not in {"match", "missing_baseline"}


__all__ = ["BaselineRecord", "DiffOutcome"]
