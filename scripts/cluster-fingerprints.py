#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Fingerprint corpus harness (v1.10.0, phase 40).

Walks a local corpus of source files (e.g. a directory of cloned AI-
generated open-source apps), counts recurring substrings within the
length window the existing catalogue uses, and prints a ranked list
of candidate patterns. The output is a human-review starting point;
nothing is auto-promoted into the catalogue.

Usage:

    uv run python scripts/cluster-fingerprints.py path/to/corpus
    uv run python scripts/cluster-fingerprints.py corpus --top 50 --min 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine.fingerprints import cluster_candidates, load_corpus_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Surface candidate fingerprints from a local source corpus."
    )
    parser.add_argument("corpus", type=Path, help="Directory tree to scan.")
    parser.add_argument("--top", type=int, default=20, help="How many candidates to print.")
    parser.add_argument("--min", type=int, default=4, help="Minimum occurrences for a candidate.")
    args = parser.parse_args()

    try:
        corpus = load_corpus_dir(args.corpus)
    except ValueError as err:
        sys.stderr.write(f"{err}\n")
        return 2

    if not corpus:
        sys.stderr.write(f"no source files matched under {args.corpus}\n")
        return 2

    candidates = cluster_candidates(corpus, min_occurrences=args.min, top_n=args.top)

    print(f"# Candidate fingerprints from {len(corpus)} files in {args.corpus}")
    print(
        "# Review each one and promote worthwhile candidates into "
        "modules/llm_audit/data/ai-app-fingerprints.yaml."
    )
    print("# columns: rank  occurrences  files  pattern")
    print()

    for idx, candidate in enumerate(candidates, start=1):
        print(
            f"{idx:>4}  {candidate.occurrences:>5}  {candidate.file_coverage:>5}  "
            f"{candidate.pattern}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
