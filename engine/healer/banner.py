"""Generated-banner / hand-edit detection (Phase 20.06, our engineering rules).

The Healer must NEVER apply a repair to a hand-owned spec. We detect
hand ownership via two complementary signals:

1. **Banner absence.** Phase 07 generated specs start with the
   ``// SENTINELQA AUTO-GENERATED ...`` banner (see Phase 07 task
   07.03). A spec without the banner is unmanaged and the Healer must
   refuse to modify it.

2. **Banner present but modified.** Even a generated spec may have been
   touched after generation. We compare a recorded ``generated_at``
   ISO-8601 timestamp inside the banner with the file's mtime. If the
   file was modified after ``generated_at`` we treat it as hand-edited.

Both checks are pure-file inspections — no git calls. Callers that
want git-aware detection can layer that on top by passing in their
own ``last_synced_at``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# The Phase-07 banner format is intentionally stable. We anchor on the
# literal prefix below and parse out the optional ``generated_at`` ISO
# timestamp from the same comment block.
_GENERATED_BANNER_PREFIX = "// SENTINELQA AUTO-GENERATED"
_GENERATED_AT_RE = re.compile(r"// generated_at:\s*([0-9TZ:\-+\.]+)")


@dataclass(frozen=True)
class BannerStatus:
    """Hand-edit status of a spec file."""

    has_banner: bool
    """True when ``// SENTINELQA AUTO-GENERATED`` is present at the head."""

    generated_at: datetime | None
    """Parsed ``// generated_at: ...`` ISO-8601 timestamp, if recorded."""

    last_modified: datetime | None
    """Filesystem mtime of the spec, if the file exists."""

    hand_edited: bool
    """``True`` when the Healer must NOT auto-apply repairs here."""

    reason: str
    """One-line human explanation. Drives the audit log entry."""


def detect_banner_status(path: Path, *, max_head_bytes: int = 4096) -> BannerStatus:
    """Inspect ``path`` and decide whether it is healer-managed.

    ``max_head_bytes`` bounds the read so large generated specs do not
    pull megabytes of source through I/O just for the banner check.
    """

    if not path.is_file():
        return BannerStatus(
            has_banner=False,
            generated_at=None,
            last_modified=None,
            hand_edited=True,
            reason="spec file does not exist (treat as hand-owned)",
        )

    head = path.read_bytes()[:max_head_bytes].decode("utf-8", errors="replace")
    has_banner = _GENERATED_BANNER_PREFIX in head
    generated_at: datetime | None = None
    match = _GENERATED_AT_RE.search(head)
    if match:
        try:
            generated_at = datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
        except ValueError:
            generated_at = None

    mtime = datetime.fromtimestamp(path.stat().st_mtime).astimezone()

    if not has_banner:
        return BannerStatus(
            has_banner=False,
            generated_at=None,
            last_modified=mtime,
            hand_edited=True,
            reason="spec missing AUTO-GENERATED banner — treating as hand-owned",
        )

    if generated_at is not None and mtime > generated_at:
        skew_s = (mtime - generated_at).total_seconds()
        # 5-second skew tolerance for filesystems with coarse mtime precision.
        if skew_s > 5.0:
            return BannerStatus(
                has_banner=True,
                generated_at=generated_at,
                last_modified=mtime,
                hand_edited=True,
                reason=(
                    f"spec modified {skew_s:.0f}s after generated_at — treating " "as hand-edited"
                ),
            )

    return BannerStatus(
        has_banner=True,
        generated_at=generated_at,
        last_modified=mtime,
        hand_edited=False,
        reason="spec is healer-managed (banner present, no detected drift)",
    )


__all__ = ["BannerStatus", "detect_banner_status"]
