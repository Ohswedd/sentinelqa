# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the fingerprint corpus harness."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.fingerprints import (
    CorpusFile,
    cluster_candidates,
    load_corpus_dir,
)


def _file(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_load_corpus_dir_picks_up_allowed_extensions(tmp_path: Path) -> None:
    _file(tmp_path / "a.tsx", "const x = 'demo/demo';")
    _file(tmp_path / "b.py", "print('hi')")
    _file(tmp_path / "c.bin", "binary")
    files = load_corpus_dir(tmp_path)
    suffixes = {f.path.suffix for f in files}
    assert ".tsx" in suffixes
    assert ".py" in suffixes
    assert ".bin" not in suffixes


def test_load_corpus_dir_skips_large_files(tmp_path: Path) -> None:
    _file(tmp_path / "big.js", "x = '" + ("a" * 300_000) + "';")
    files = load_corpus_dir(tmp_path, max_file_bytes=1024)
    assert files == ()


def test_load_corpus_dir_rejects_non_directory(tmp_path: Path) -> None:
    bogus = tmp_path / "nope"
    with pytest.raises(ValueError):
        load_corpus_dir(bogus)


def test_cluster_surfaces_repeated_substring(tmp_path: Path) -> None:
    # Same recognizable line in 5 files.
    line = "const apiKey = 'pk_demo_AAAAAAAAAAAA';"
    for i in range(5):
        _file(tmp_path / f"app_{i}.ts", f"// banner\n{line}\nconsole.log('x');")
    corpus = load_corpus_dir(tmp_path)

    candidates = cluster_candidates(corpus, min_occurrences=3, top_n=5)
    assert any(c.pattern == line for c in candidates)


def test_cluster_drops_universal_noise() -> None:
    corpus = (
        CorpusFile(
            path=Path("a.ts"),
            body="\n".join(
                [
                    "import { x } from 'foo';",
                    "export const x = 'pk_demo_AAAAAAAAAAAA';",
                ]
                * 10
            ),
        ),
    )
    candidates = cluster_candidates(corpus, min_occurrences=2, top_n=5)
    patterns = {c.pattern for c in candidates}
    assert all(not p.startswith("import ") for p in patterns)
    assert all(not p.startswith("export ") for p in patterns)


def test_cluster_ranks_by_occurrences_and_coverage(tmp_path: Path) -> None:
    rare_line = "const k = 'rare_AAAAAAAAAAAAAA';"
    common_line = "const c = 'common_AAAAAAAAAAA';"
    # `common_line` appears once in each of 5 files (5 occurrences x 5 files = 25).
    for i in range(5):
        _file(tmp_path / f"app_{i}.ts", f"{common_line}")
    # `rare_line` appears 5 times but only in one file (5 x 1 = 5).
    _file(tmp_path / "only.ts", "\n".join([rare_line] * 5))
    corpus = load_corpus_dir(tmp_path)
    candidates = cluster_candidates(corpus, min_occurrences=3, top_n=5)
    common_candidate = next(c for c in candidates if c.pattern == common_line)
    rare_candidate = next(c for c in candidates if c.pattern == rare_line)
    assert common_candidate.rank_score > rare_candidate.rank_score


def test_cluster_respects_min_occurrences(tmp_path: Path) -> None:
    _file(tmp_path / "a.ts", "const x = 'pk_demo_AAAAAAAAAAAAAAAA';")
    corpus = load_corpus_dir(tmp_path)
    candidates = cluster_candidates(corpus, min_occurrences=5, top_n=5)
    assert candidates == ()


def test_cluster_returns_empty_for_empty_corpus() -> None:
    assert cluster_candidates([], min_occurrences=2, top_n=5) == ()


def test_cluster_top_n_caps_output(tmp_path: Path) -> None:
    for i in range(30):
        _file(
            tmp_path / f"app_{i}.ts",
            "\n".join(f"const v_{j} = 'AAAAAAAAAAAAAAAA_{j}';" for j in range(8)),
        )
    corpus = load_corpus_dir(tmp_path)
    candidates = cluster_candidates(corpus, min_occurrences=3, top_n=5)
    assert len(candidates) <= 5
