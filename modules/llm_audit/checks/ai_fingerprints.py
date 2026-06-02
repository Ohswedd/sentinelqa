# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""LLM-AI-FINGERPRINT — match LLM-built-app fingerprints (v1.9.0).

The fingerprint catalogue lives at
``modules/llm_audit/data/ai-app-fingerprints.yaml``. Each entry is a
high-precision regex scoped to either source files or rendered text;
matches translate to :class:`CheckFinding` records carrying the
per-fingerprint severity, confidence, and human-readable title.

The catalogue is data-driven so growth (adding new patterns,
adjusting severity) doesn't require code edits. Reviewers must keep
patterns high-signal: a fingerprint that matches a well-known
open-source clean codebase is a fingerprint we delete.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

import yaml
from engine.domain.finding import Severity

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import RenderedTextSample, SourceFile
from modules.llm_audit.rules import LLM_AI_APP_FINGERPRINT

FingerprintTarget = Literal["source", "rendered"]

_DEFAULT_CATALOGUE_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent / "data" / "ai-app-fingerprints.yaml"
)


@dataclass(frozen=True, slots=True)
class Fingerprint:
    """One catalogue entry compiled and ready to match."""

    id: str
    target: FingerprintTarget
    category: str
    severity: Severity
    confidence: float
    title: str
    description: str
    pattern: re.Pattern[str]


def load_fingerprints(path: Path | None = None) -> tuple[Fingerprint, ...]:
    """Load and compile the fingerprint catalogue.

    Defaults to the in-tree catalogue under
    ``modules/llm_audit/data/ai-app-fingerprints.yaml``. Callers may
    supply an override for tests or for site-local catalogues.
    """

    return _load_cached(str(path) if path is not None else str(_DEFAULT_CATALOGUE_PATH))


@lru_cache(maxsize=4)
def _load_cached(path_str: str) -> tuple[Fingerprint, ...]:
    path = Path(path_str)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    fingerprints_raw = payload.get("fingerprints", [])
    if not isinstance(fingerprints_raw, list):
        raise ValueError(f"{path}: 'fingerprints' must be a list")
    out: list[Fingerprint] = []
    for entry in fingerprints_raw:
        out.append(_compile_entry(entry, source=path))
    return tuple(out)


def _compile_entry(entry: object, *, source: Path) -> Fingerprint:
    if not isinstance(entry, dict):
        raise ValueError(f"{source}: fingerprint entries must be mappings")
    target = entry.get("target")
    if target not in ("source", "rendered"):
        raise ValueError(
            f"{source}: fingerprint {entry.get('id')!r}: "
            f"'target' must be 'source' or 'rendered'; got {target!r}"
        )
    severity = entry.get("severity")
    if severity not in ("critical", "high", "medium", "low", "info"):
        raise ValueError(
            f"{source}: fingerprint {entry.get('id')!r}: "
            f"'severity' must be a valid Severity; got {severity!r}"
        )
    pattern_raw = entry.get("pattern")
    if not isinstance(pattern_raw, str):
        raise ValueError(f"{source}: fingerprint {entry.get('id')!r}: 'pattern' must be a string")
    return Fingerprint(
        id=str(entry["id"]),
        target=target,
        category=str(entry.get("category", "uncategorized")),
        severity=severity,
        confidence=float(entry.get("confidence", LLM_AI_APP_FINGERPRINT.confidence)),
        title=str(entry.get("title", entry["id"])),
        description=str(entry.get("description", "")).strip(),
        pattern=re.compile(pattern_raw, re.IGNORECASE | re.MULTILINE),
    )


def check_ai_fingerprints(
    source_files: Iterable[SourceFile],
    rendered_text: Iterable[RenderedTextSample],
    *,
    catalogue: Sequence[Fingerprint] | None = None,
) -> tuple[CheckFinding, ...]:
    """Match every catalogue entry against the right input set.

    Returns one :class:`CheckFinding` per (fingerprint, match site)
    pair. The same fingerprint matching two distinct routes emits two
    findings; the same fingerprint matching twice within one source
    file emits one finding (first-match wins, mirrors the pattern used
    by :func:`modules.llm_audit.checks.coming_soon.check_coming_soon`).
    """

    catalogue = catalogue if catalogue is not None else load_fingerprints()
    if not catalogue:
        return ()

    out: list[CheckFinding] = []
    source_list = list(source_files)
    rendered_list = list(rendered_text)

    for fingerprint in catalogue:
        if fingerprint.target == "source":
            out.extend(_match_against_sources(fingerprint, source_list))
        else:
            out.extend(_match_against_rendered(fingerprint, rendered_list))

    return tuple(out)


def _match_against_sources(
    fingerprint: Fingerprint, source_files: Sequence[SourceFile]
) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    for source in source_files:
        match = fingerprint.pattern.search(source.body)
        if not match:
            continue
        findings.append(
            CheckFinding(
                rule_id=LLM_AI_APP_FINGERPRINT.id,
                title=fingerprint.title,
                description=(
                    f"{fingerprint.description}\n\n" f"Matched in source file: {source.path}"
                ),
                file=source.path,
                snippet=_snippet(source.body, match),
                severity_override=fingerprint.severity,
                confidence_override=fingerprint.confidence,
                extra_context=(
                    ("fingerprint_id", fingerprint.id),
                    ("fingerprint_category", fingerprint.category),
                ),
            )
        )
    return findings


def _match_against_rendered(
    fingerprint: Fingerprint, samples: Sequence[RenderedTextSample]
) -> list[CheckFinding]:
    findings: list[CheckFinding] = []
    for sample in samples:
        match = fingerprint.pattern.search(sample.text)
        if not match:
            continue
        findings.append(
            CheckFinding(
                rule_id=LLM_AI_APP_FINGERPRINT.id,
                title=fingerprint.title,
                description=(
                    f"{fingerprint.description}\n\n" f"Matched on route: {sample.route_url}"
                ),
                route=sample.route_url,
                selector=sample.selector,
                snippet=_snippet(sample.text, match),
                severity_override=fingerprint.severity,
                confidence_override=fingerprint.confidence,
                extra_context=(
                    ("fingerprint_id", fingerprint.id),
                    ("fingerprint_category", fingerprint.category),
                    ("priority", sample.priority),
                ),
            )
        )
    return findings


def _snippet(body: str, match: re.Match[str]) -> str:
    """Return a short context window around the match, single-lined."""

    start = max(0, match.start() - 40)
    end = min(len(body), match.end() + 40)
    return body[start:end].replace("\n", " ").strip()


__all__ = [
    "Fingerprint",
    "FingerprintTarget",
    "check_ai_fingerprints",
    "load_fingerprints",
]
