# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Fingerprint mining helpers (v1.10.0, phase 40).

The hand-curated catalogue ships at
``modules/llm_audit/data/ai-app-fingerprints.yaml``. This module gives
reviewers a tool to grow it: feed in a corpus of source files (e.g. a
checked-out tree of AI-built apps), and the analyser surfaces
high-frequency, low-distribution substrings that are candidate
fingerprints.

Output is a ranked list of candidates; a human reviews and promotes
the worthwhile ones into the YAML catalogue. We deliberately do not
auto-write to the catalogue — false positives in catalogue patterns
become false-positive findings in user runs.
"""

from __future__ import annotations

from engine.fingerprints.corpus import (
    Candidate,
    CorpusFile,
    cluster_candidates,
    load_corpus_dir,
)

__all__ = [
    "Candidate",
    "CorpusFile",
    "cluster_candidates",
    "load_corpus_dir",
]
