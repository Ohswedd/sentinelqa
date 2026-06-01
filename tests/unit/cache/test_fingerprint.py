# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the source fingerprint."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.cache.fingerprint import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_INCLUDE_SUFFIXES,
    SourceFingerprint,
    compute_fingerprint,
)


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_fingerprint_is_deterministic(tmp_path: Path) -> None:
    """The same tree, hashed twice, must yield the same hash."""

    _write(tmp_path / "src" / "main.py", "print('hi')\n")
    _write(tmp_path / "src" / "lib.ts", "export const x = 1;\n")
    first = compute_fingerprint(tmp_path)
    second = compute_fingerprint(tmp_path)
    assert first == second
    assert first.file_count == 2
    assert first.total_bytes > 0
    assert len(first.hash) == 64


def test_fingerprint_changes_when_content_changes(tmp_path: Path) -> None:
    target = _write(tmp_path / "src" / "main.py", "a\n")
    before = compute_fingerprint(tmp_path)
    target.write_text("b\n", encoding="utf-8")
    after = compute_fingerprint(tmp_path)
    assert before.hash != after.hash


def test_fingerprint_changes_when_files_added(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "main.py", "x\n")
    before = compute_fingerprint(tmp_path)
    _write(tmp_path / "src" / "extra.py", "y\n")
    after = compute_fingerprint(tmp_path)
    assert before.hash != after.hash
    assert after.file_count == before.file_count + 1


def test_fingerprint_changes_on_rename(tmp_path: Path) -> None:
    """Renaming a file must invalidate the fingerprint even when content is identical."""

    src = _write(tmp_path / "src" / "before.py", "same\n")
    before = compute_fingerprint(tmp_path)
    src.rename(tmp_path / "src" / "after.py")
    after = compute_fingerprint(tmp_path)
    assert before.hash != after.hash


def test_fingerprint_skips_excluded_directories(tmp_path: Path) -> None:
    """``node_modules``, ``.git``, ``.venv`` must never be hashed."""

    _write(tmp_path / "src" / "main.py", "x\n")
    _write(tmp_path / "node_modules" / "lib" / "index.js", "y\n")
    _write(tmp_path / ".venv" / "site-packages" / "z.py", "z\n")
    fp = compute_fingerprint(tmp_path)
    assert fp.file_count == 1


def test_fingerprint_skips_unknown_suffixes(tmp_path: Path) -> None:
    """Binary blobs, images, etc. are not in the source surface."""

    _write(tmp_path / "src" / "main.py", "x\n")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    (tmp_path / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp4")
    fp = compute_fingerprint(tmp_path)
    assert fp.file_count == 1


def test_fingerprint_includes_known_basenames(tmp_path: Path) -> None:
    """``package.json``, ``Dockerfile`` etc. must be hashed even without standard suffix."""

    _write(tmp_path / "Dockerfile", "FROM scratch\n")
    _write(tmp_path / "package.json", '{"name": "x"}\n')
    fp = compute_fingerprint(tmp_path)
    assert fp.file_count == 2


def test_fingerprint_short_returns_12_chars() -> None:
    fp = SourceFingerprint(hash="a" * 64, file_count=1, total_bytes=10)
    assert fp.short() == "aaaaaaaaaaaa"
    assert len(fp.short()) == 12


def test_fingerprint_empty_tree_returns_known_zero_state(tmp_path: Path) -> None:
    fp = compute_fingerprint(tmp_path)
    assert fp.file_count == 0
    assert fp.total_bytes == 0


def test_custom_excludes_are_respected(tmp_path: Path) -> None:
    _write(tmp_path / "keep" / "k.py", "k\n")
    _write(tmp_path / "skipme" / "s.py", "s\n")
    custom = frozenset({*DEFAULT_EXCLUDE_DIRS, "skipme"})
    fp = compute_fingerprint(tmp_path, exclude_dirs=custom)
    assert fp.file_count == 1


def test_default_includes_cover_common_web_stack() -> None:
    for ext in (".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte"):
        assert ext in DEFAULT_INCLUDE_SUFFIXES


@pytest.mark.parametrize("dirname", [".git", "node_modules", ".venv", "__pycache__"])
def test_default_excludes_cover_canonical_dirs(dirname: str) -> None:
    assert dirname in DEFAULT_EXCLUDE_DIRS


def test_fingerprint_is_path_separator_normalised(tmp_path: Path, monkeypatch) -> None:
    """Path separators must be normalised to POSIX before hashing."""

    _write(tmp_path / "a" / "b" / "c.py", "x\n")
    fp_first = compute_fingerprint(tmp_path)
    fp_second = compute_fingerprint(tmp_path)
    assert fp_first.hash == fp_second.hash
