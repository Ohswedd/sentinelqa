"""recurring secret-leak audit over persisted run artifacts.

The intent of this test is **not** to test the redactor (that is covered by
``tests/unit/redact/``). It is to verify, on every CI run, that **no checked-in
or freshly-produced** ``.sentinel/runs/<id>/`` artifact contains a credential
the redactor missed.

The audit walks the live ``.sentinel/runs/`` tree if one exists; otherwise it
falls back to scanning the curated golden artifacts under
``tests/golden/reports/``. Either way, a regression in the redactor or in a
new writer will be caught by this gate before it ships.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNS_DIR = REPO_ROOT / ".sentinel" / "runs"
GOLDEN_DIR = REPO_ROOT / "tests" / "golden" / "reports"


# Patterns are anchored on shapes the redactor MUST strip before disk.
# Each pattern is paired with an explicit reason so a failure message reads
# usefully.
PATTERNS: dict[str, tuple[re.Pattern[str], str]] = {
    "pem_private_key": (
        re.compile(r"-----BEGIN ([A-Z]+ )?PRIVATE KEY-----"),
        "raw PEM private-key header in an artifact",
    ),
    "ssh_private_key": (
        re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"),
        "raw OpenSSH private-key header in an artifact",
    ),
    "aws_access_key": (
        re.compile(r"AKIA[0-9A-Z]{16}"),
        "AWS access-key ID shape",
    ),
    "stripe_live_key": (
        re.compile(r"sk_live_[0-9a-zA-Z]{24,}"),
        "Stripe live secret-key shape",
    ),
    "github_token": (
        re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
        "GitHub personal-/oauth-token shape",
    ),
    "slack_token": (
        re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),
        "Slack token shape",
    ),
    "google_api_key": (
        re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
        "Google API key shape",
    ),
    "openai_sk_key": (
        re.compile(r"sk-(proj-)?[A-Za-z0-9]{40,}"),
        "OpenAI secret-key shape",
    ),
    "anthropic_key": (
        re.compile(r"sk-ant-[A-Za-z0-9_-]{40,}"),
        "Anthropic API-key shape",
    ),
    "jwt": (
        re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),
        "JWT shape (header.payload.signature)",
    ),
    # Authorization header with a Bearer that is NOT redacted. The redactor
    # writes the literal token "[REDACTED:" so we exclude those captures.
    "authorization_bearer_real": (
        re.compile(r"(?i)Authorization\s*:\s*Bearer\s+[A-Za-z0-9_\-\.]{20,}"),
        "Authorization: Bearer with an unredacted token",
    ),
}


# Only scan actual artifact extensions. The fallback path walks
# `tests/golden/reports/`, which co-locates byte-locked goldens with the
# Python *writer tests* that build them — those test files legitimately
# carry redactor fixtures and would falsely trip the secret-shape gates.
# Real shipped artifacts only ever use the extensions below; everything
# else (.py/.pyc/__pycache__/.so/.dylib) is out-of-scope.
_ARTIFACT_EXTENSIONS: frozenset[str] = frozenset(
    {".json", ".html", ".md", ".xml", ".yaml", ".yml", ".log", ".jsonl", ".txt"}
)


def _iter_artifact_files() -> list[Path]:
    """Return every artifact path we want to scan, deduplicated and sorted."""

    if RUNS_DIR.exists() and any(RUNS_DIR.iterdir()):
        candidates = RUNS_DIR.rglob("*")
    else:
        # Fallback: the curated reporter goldens. These are byte-stable
        # inputs to the writers, so a regression there would surface in a
        # developer's first local run.
        candidates = GOLDEN_DIR.rglob("*")
    return sorted(
        p
        for p in candidates
        if p.is_file() and "__pycache__" not in p.parts and p.suffix.lower() in _ARTIFACT_EXTENSIONS
    )


_SCAN_TARGETS = _iter_artifact_files()


def test_scan_inputs_are_non_empty() -> None:
    """Guardrail: we must be scanning *something*."""

    assert _SCAN_TARGETS, (
        "Neither .sentinel/runs/ nor tests/golden/reports/ contained any "
        "files to scan. The secret-leak audit cannot certify an empty set."
    )


@pytest.mark.parametrize("rule_name,probe", list(PATTERNS.items()))
def test_no_unredacted_secrets_match_pattern(
    rule_name: str, probe: tuple[re.Pattern[str], str]
) -> None:
    pattern, reason = probe
    hits: list[tuple[Path, str]] = []
    for path in _SCAN_TARGETS:
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            # Skip unreadable files (e.g. dangling symlink in a deleted run);
            # there is nothing to leak there.
            continue
        for match in pattern.finditer(text):
            sample = match.group(0)
            if rule_name == "authorization_bearer_real" and "REDACTED" in sample:
                continue
            hits.append((path, sample[:120]))

    if hits:
        lines = "\n".join(
            f"  - {path.relative_to(REPO_ROOT)}: {sample!r}" for path, sample in hits[:5]
        )
        more = "" if len(hits) <= 5 else f"\n  ... and {len(hits) - 5} more"
        pytest.fail(
            f"Found {len(hits)} unredacted secret-shaped match(es) for rule "
            f"{rule_name!r} ({reason}):\n{lines}{more}\n\n"
            "The redactor at engine.policy.redaction.redact must strip this "
            "shape before it reaches disk."
        )


def test_sentinel_runs_have_no_unredacted_secrets() -> None:
    """Sweep all patterns in one go so the failure message lists every hit at once."""

    failures: list[str] = []
    for rule_name, (pattern, reason) in PATTERNS.items():
        for path in _SCAN_TARGETS:
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            for match in pattern.finditer(text):
                sample = match.group(0)
                if rule_name == "authorization_bearer_real" and "REDACTED" in sample:
                    continue
                rel = path.relative_to(REPO_ROOT)
                failures.append(f"[{rule_name}] {reason} — {rel}: {sample[:80]!r}")
    assert not failures, "Unredacted secret-shaped content in artifacts:\n" + "\n".join(failures)
