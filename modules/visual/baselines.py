"""Baseline storage layout.

The baseline tree mirrors the capture tree:

::

 <baselines_dir>/
 <viewport>/
 <route-slug>.png
 index.json

``index.json`` records one row per stored baseline (sha256, captured-at,
captured-by-run-id, masks-applied) so we can detect tampering and
attribute who promoted each baseline. The format is intentionally a
flat JSON object — schema version ``"1"`` until we have a structural
change to justify a bump.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Iterable
from pathlib import Path

from PIL import Image

from modules.visual.models import BaselineRecord

INDEX_SCHEMA_VERSION = "1"
INDEX_FILENAME = "index.json"

_ROUTE_SAFE = re.compile(r"[^a-z0-9._-]+")


def slugify_route(route: str) -> str:
    """Return the on-disk file segment for a captured route.

    The slug rules: lowercase, replace any run of unsafe chars with
    a single ``_``, strip leading/trailing ``_``. Empty strings collapse
    to ``root``. Matches the contract the TS capture helper will follow
    when emitting filenames (so baselines line up).
    """

    lowered = route.strip().lower()
    if not lowered or lowered in {"/", ""}:
        return "root"
    cleaned = _ROUTE_SAFE.sub("_", lowered).strip("_")
    return cleaned or "root"


def baseline_path(baselines_dir: Path, viewport: str, route_slug: str) -> Path:
    """Return the on-disk path for one baseline PNG."""

    return baselines_dir / viewport / f"{route_slug}.png"


def sha256_file(path: Path) -> str:
    """Return the hex sha256 of ``path``."""

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_index(baselines_dir: Path) -> dict[tuple[str, str], BaselineRecord]:
    """Return ``{(viewport, route_slug): BaselineRecord}``.

    Returns an empty mapping when ``index.json`` does not exist (first
    run). Raises :class:`ValueError` when the file is present but
    malformed (corrupt JSON, missing required fields) — the caller is
    expected to surface that as an E-CFG-style error.
    """

    index_path = baselines_dir / INDEX_FILENAME
    if not index_path.exists():
        return {}
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"visual: baselines index at {index_path} is not valid JSON: {exc}"
        ) from exc
    rows = payload.get("baselines") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"visual: baselines index at {index_path} is missing 'baselines' array.")
    out: dict[tuple[str, str], BaselineRecord] = {}
    for row in rows:
        try:
            record = BaselineRecord(
                viewport=str(row["viewport"]),
                route_slug=str(row["route_slug"]),
                path=str(row["path"]),
                width=int(row["width"]),
                height=int(row["height"]),
                sha256=str(row["sha256"]),
                captured_at=str(row["captured_at"]),
                captured_by_run_id=str(row["captured_by_run_id"]),
                masks_applied=tuple(str(m) for m in row.get("masks_applied", [])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"visual: malformed baselines row in {index_path}: {row!r} ({exc})"
            ) from exc
        out[(record.viewport, record.route_slug)] = record
    return out


def write_index(
    baselines_dir: Path,
    records: Iterable[BaselineRecord],
) -> Path:
    """Persist the index atomically (write to ``*.tmp``, then rename)."""

    baselines_dir.mkdir(parents=True, exist_ok=True)
    index_path = baselines_dir / INDEX_FILENAME
    payload = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "baselines": [
            {
                "viewport": r.viewport,
                "route_slug": r.route_slug,
                "path": r.path,
                "width": r.width,
                "height": r.height,
                "sha256": r.sha256,
                "captured_at": r.captured_at,
                "captured_by_run_id": r.captured_by_run_id,
                "masks_applied": list(r.masks_applied),
            }
            for r in sorted(records, key=lambda r: (r.viewport, r.route_slug))
        ],
    }
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    tmp_path = index_path.with_suffix(".json.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(index_path)
    return index_path


def promote_to_baseline(
    *,
    baselines_dir: Path,
    viewport: str,
    route_slug: str,
    source_png: Path,
    captured_by_run_id: str,
    captured_at: str,
    masks_applied: tuple[str, ...] = (),
) -> BaselineRecord:
    """Copy ``source_png`` into the baseline tree and return the record.

    The destination is overwritten atomically. The caller is responsible
    for the CI-acceptance guard (see :func:`apps/cli sentinel visual`).
    """

    if not source_png.exists():
        raise FileNotFoundError(f"visual: source PNG {source_png} does not exist.")
    dest = baseline_path(baselines_dir, viewport, route_slug)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".png.tmp")
    shutil.copyfile(source_png, tmp)
    tmp.replace(dest)
    with Image.open(dest) as img:
        width, height = img.size
    return BaselineRecord(
        viewport=viewport,
        route_slug=route_slug,
        path=str(dest.relative_to(baselines_dir)).replace("\\", "/"),
        width=width,
        height=height,
        sha256=sha256_file(dest),
        captured_at=captured_at,
        captured_by_run_id=captured_by_run_id,
        masks_applied=tuple(masks_applied),
    )


__all__ = [
    "INDEX_FILENAME",
    "INDEX_SCHEMA_VERSION",
    "baseline_path",
    "load_index",
    "promote_to_baseline",
    "sha256_file",
    "slugify_route",
    "write_index",
]
