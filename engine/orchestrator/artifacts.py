"""Run artifact tree per CLAUDE §11 (task 02.05).

Each run lives at ``.sentinel/runs/<run-id>/``. Files are created on
demand (CLAUDE §11: "when available") and writes are atomic (write to
a sibling ``*.tmp`` then ``os.replace``). Sensitive payloads pass
through :func:`engine.policy.redaction.redact` before JSON
serialization.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from engine.policy.redaction import redact


class ArtifactDirectory:
    """Filesystem handle for one run's artifact tree."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @classmethod
    def create(cls, base: Path, run_id: str) -> ArtifactDirectory:
        """Create the run directory under ``base`` and return a handle."""

        run_dir = base / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return cls(run_dir)

    @property
    def root(self) -> Path:
        return self._root

    def path(self, name: str) -> Path:
        return self._root / name

    def subdir(self, name: str) -> Path:
        out = self._root / name
        out.mkdir(parents=True, exist_ok=True)
        return out

    def write_json(self, name: str, obj: Any) -> Path:
        # `_jsonable` first so domain objects / Pydantic models / Paths
        # become primitives; THEN `redact` so secret keys and values are
        # masked. Reversing the order causes redact to coerce Path objects
        # via repr() rather than str().
        return self._atomic_write(
            name,
            json.dumps(redact(_jsonable(obj)), sort_keys=True, indent=2, default=str) + "\n",
        )

    def write_yaml(self, name: str, obj: Any) -> Path:
        return self._atomic_write(
            name,
            yaml.safe_dump(redact(_jsonable(obj)), sort_keys=True, default_flow_style=False),
        )

    def write_text(self, name: str, text: str) -> Path:
        return self._atomic_write(name, text)

    def append_line(self, name: str, line: str) -> Path:
        """Append a line to a file (creates if missing). NOT atomic — used
        for the audit log which already serializes one record per line."""

        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not line.endswith("\n"):
            line += "\n"
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line)
        return target

    def _atomic_write(self, name: str, content: str) -> Path:
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(target.parent),
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as fh:
            fh.write(content)
            fh.flush()
            # Some filesystems (tmpfs, network mounts) don't support fsync;
            # tolerate that but skip the durability gain.
            with contextlib.suppress(OSError):
                os.fsync(fh.fileno())
            tmp_path = Path(fh.name)
        os.replace(tmp_path, target)
        return target


def _jsonable(value: Any) -> Any:
    """Coerce Pydantic models / Paths / sets to JSON-friendly primitives."""

    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return _jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):  # noqa: UP038
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def list_runs(base: Path) -> list[Path]:
    """Return run directories under ``base`` newest-first."""

    if not base.exists():
        return []
    entries: Iterable[Path] = (p for p in base.iterdir() if p.is_dir() and p.name != "latest")
    return sorted(entries, key=lambda p: p.stat().st_mtime, reverse=True)


__all__ = ["ArtifactDirectory", "list_runs"]
