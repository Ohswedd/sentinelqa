"""Schema version constants for every machine-readable SentinelQA artifact.

Single source of truth referenced by domain models, report writers (Phase 03),
the SDK (Phase 16), and CI schema-validation hooks. Changing a constant here
is a breaking change and requires an ADR per CLAUDE.md §34 (Report schema /
Config schema triggers) and a note in `docs/dev/schema-versioning.md`.

Each value is a major-version string (e.g. ``"1"``). Minor/patch additions
that remain backwards-compatible do NOT bump the constant; breaking changes
do, and they ship with a migration in ``engine/domain/migrations/``.
"""

from __future__ import annotations

from typing import Final

# Per-artifact schema versions. Every machine-readable artifact root MUST
# include a ``schema_version`` field equal to its constant here.
RUN_SCHEMA_VERSION: Final[str] = "1"
"""Version of `run.json` and the in-memory ``TestRun`` model."""

FINDINGS_SCHEMA_VERSION: Final[str] = "2"
"""Version of `findings.json` and the in-memory ``Finding`` model (PRD §18.2).

v2 (Phase 32, ADR-0044) adds three optional taxonomy ids — ``cwe_id``,
``attack_id``, ``owasp_api_id`` — so SARIF / dashboard consumers can
deep-link findings to ``cwe.mitre.org``, ``attack.mitre.org``, and the
OWASP API Top-10. v1 documents parse cleanly into the v2 model (the new
fields default to ``None``); the migration in
``engine/domain/migrations/findings_1_to_2.py`` makes the upgrade
explicit when callers persist v1 inputs back as v2.
"""

SCORE_SCHEMA_VERSION: Final[str] = "1"
"""Version of `score.json` and the in-memory ``QualityScore`` model (PRD §19)."""

CONFIG_SCHEMA_VERSION: Final[str] = "1"
"""Version of `sentinel.config.yaml` accepted by the loader (PRD §17)."""

REPAIR_SUGGESTION_SCHEMA_VERSION: Final[str] = "1"
"""Version of healer ``RepairSuggestion`` artifacts (PRD §9.6, CLAUDE.md §23)."""

AGENT_MESSAGE_SCHEMA_VERSION: Final[str] = "1"
"""Version of agent-facing message envelopes (PRD §16, Phase 18)."""


# Convenience map for documentation / introspection. Keyed by the symbolic
# name that ships in the artifact root; values are the canonical constants.
ALL_SCHEMA_VERSIONS: Final[dict[str, str]] = {
    "run": RUN_SCHEMA_VERSION,
    "findings": FINDINGS_SCHEMA_VERSION,
    "score": SCORE_SCHEMA_VERSION,
    "config": CONFIG_SCHEMA_VERSION,
    "repair_suggestion": REPAIR_SUGGESTION_SCHEMA_VERSION,
    "agent_message": AGENT_MESSAGE_SCHEMA_VERSION,
}


__all__ = [
    "RUN_SCHEMA_VERSION",
    "FINDINGS_SCHEMA_VERSION",
    "SCORE_SCHEMA_VERSION",
    "CONFIG_SCHEMA_VERSION",
    "REPAIR_SUGGESTION_SCHEMA_VERSION",
    "AGENT_MESSAGE_SCHEMA_VERSION",
    "ALL_SCHEMA_VERSIONS",
]
