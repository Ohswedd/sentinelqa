"""Maintain `.sentinel/runs/latest`.

POSIX gets a symlink; Windows gets a regular file pointing at the run
id (a "marker file") because creating directory symlinks requires
admin rights or developer mode.
"""

from __future__ import annotations

import os
from pathlib import Path


def update_latest_pointer(root: Path, run_dir: Path) -> Path:
    """Update ``root/latest`` to refer to ``run_dir`` (relative path)."""

    root.mkdir(parents=True, exist_ok=True)
    latest = root / "latest"

    if latest.exists() or latest.is_symlink():
        if latest.is_symlink() or latest.is_file():
            latest.unlink()
        else:
            # Directory replacement is not a valid path here — bail out.
            raise OSError(f"Refusing to overwrite directory at {latest}.")

    relative = Path(os.path.relpath(run_dir, root))

    if os.name == "nt":  # pragma: no cover - Windows fallback
        latest.write_text(str(relative), encoding="utf-8")
        return latest

    os.symlink(str(relative), str(latest), target_is_directory=True)
    return latest


__all__ = ["update_latest_pointer"]
