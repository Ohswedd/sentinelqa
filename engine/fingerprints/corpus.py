# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Candidate-pattern discovery from a corpus of source files.

The clustering approach is intentionally simple: count repeating
substrings of length 12-80 chars, rank by
``occurrences * file_coverage``, and drop ones that match well-known
universal strings (HTML doctype, license headers, etc.). This isn't
an embedding-based clusterer — false positives there would land in
the catalogue silently. A human review step is mandatory.

Public entry points:

* :class:`CorpusFile` — one file in the input corpus.
* :func:`load_corpus_dir` — walk a directory tree and load files
  matching the extension allowlist.
* :class:`Candidate` — a ranked candidate pattern.
* :func:`cluster_candidates` — produce the ranked list.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# Substring length window. Below 12 chars we'd match every keyword; above
# 80 chars we'd miss recurring snippets that vary only in trailing
# whitespace.
_MIN_LEN: Final[int] = 12
_MAX_LEN: Final[int] = 80
_DEFAULT_MIN_OCCURRENCES: Final[int] = 4
_DEFAULT_TOP_N: Final[int] = 20

_ALLOWED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".js", ".jsx", ".ts", ".tsx", ".py", ".html", ".css", ".vue", ".svelte"}
)

# Drop candidates that are essentially universal — they'd match every
# project. The list intentionally short; we err on letting candidates
# through and rely on the human review step.
_UNIVERSAL_NOISE: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^\s*$"),
    re.compile(r"^[A-Za-z_]+$"),  # single token
    re.compile(r"^\s*<!doctype", re.IGNORECASE),
    re.compile(r"^\s*Copyright"),
    re.compile(r"^\s*SPDX-License"),
    re.compile(r"^\s*Permission is hereby"),
    re.compile(r"^\s*import\s"),  # generic Python / JS import lines
    re.compile(r"^\s*export\s"),
)


@dataclass(frozen=True, slots=True)
class CorpusFile:
    """One file in the input corpus."""

    path: Path
    body: str


@dataclass(frozen=True, slots=True)
class Candidate:
    """One candidate pattern surfaced by clustering."""

    pattern: str
    occurrences: int
    file_coverage: int  # number of files the pattern appears in
    rank_score: float  # occurrences * file_coverage (post-noise drop)


def load_corpus_dir(
    root: Path,
    *,
    extensions: frozenset[str] = _ALLOWED_EXTENSIONS,
    max_file_bytes: int = 250_000,
) -> tuple[CorpusFile, ...]:
    """Walk ``root`` and load every file whose suffix is in ``extensions``.

    Files larger than ``max_file_bytes`` are skipped (we'd rather miss
    a huge minified bundle than blow up memory).
    """

    if not root.is_dir():
        raise ValueError(f"corpus root not a directory: {root}")

    out: list[CorpusFile] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(body) > max_file_bytes:
            continue
        out.append(CorpusFile(path=path, body=body))
    return tuple(out)


def cluster_candidates(
    corpus: Iterable[CorpusFile],
    *,
    min_occurrences: int = _DEFAULT_MIN_OCCURRENCES,
    top_n: int = _DEFAULT_TOP_N,
) -> tuple[Candidate, ...]:
    """Return the top-N candidate patterns from ``corpus``.

    The default thresholds (>=4 occurrences across the corpus, top 20)
    are tuned for a corpus of ~10-50 small apps. Pass larger values
    for bigger corpora.
    """

    occurrences: Counter[str] = Counter()
    file_coverage: dict[str, set[Path]] = {}

    for entry in corpus:
        seen_in_file: set[str] = set()
        for line in entry.body.splitlines():
            stripped = line.strip()
            if not stripped or _is_noise(stripped):
                continue
            # We slice the full line as a candidate; long lines yield
            # one candidate, short ones get the natural windowing for
            # free.
            if _MIN_LEN <= len(stripped) <= _MAX_LEN:
                occurrences[stripped] += 1
                seen_in_file.add(stripped)
        for token in seen_in_file:
            file_coverage.setdefault(token, set()).add(entry.path)

    ranked: list[Candidate] = []
    for pattern, count in occurrences.items():
        if count < min_occurrences:
            continue
        coverage = len(file_coverage.get(pattern, ()))
        ranked.append(
            Candidate(
                pattern=pattern,
                occurrences=count,
                file_coverage=coverage,
                rank_score=float(count * coverage),
            )
        )

    ranked.sort(key=lambda c: (-c.rank_score, c.pattern))
    return tuple(ranked[:top_n])


def _is_noise(line: str) -> bool:
    return any(noise.search(line) for noise in _UNIVERSAL_NOISE)


__all__ = [
    "Candidate",
    "CorpusFile",
    "cluster_candidates",
    "load_corpus_dir",
]
