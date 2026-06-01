"""Slack summary payload generator (, ).

Produces a Slack Block Kit JSON payload summarizing a SentinelQA run.
The payload is NOT posted by this module — owns the Slack
integration. Here we only generate the JSON envelope so the workflow,
shape, and contract are testable today.

The output is validated against a vendored Block Kit subset schema at
``packages/shared-schema/external/slack-block-kit.schema.json``. The
full upstream Block Kit reference lives at https://api.slack.com/block-kit.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from engine.domain.finding import Finding, Severity
from engine.domain.policy_decision import PolicyDecision, ReleaseDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.reporter.markdown_writer import (
    RELEASE_DECISION_LABEL,
    SEVERITY_LABEL,
    SEVERITY_ORDER,
)

SLACK_PAYLOAD_SCHEMA_PATH: Final[Path] = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "shared-schema"
    / "external"
    / "slack-block-kit.schema.json"
)

_TOP_BLOCKER_LIMIT: Final[int] = 3


def render_slack_payload(
    run: TestRun,
    findings: Sequence[Finding],
    score: QualityScore | None,
    policy: PolicyDecision | None,
    *,
    artifact_url: str | None = None,
) -> dict[str, Any]:
    """Build the Block Kit payload.

    Returns a plain dict so callers can write it to JSON, pass it to a
    HTTP client, or post it via the Slack SDK in.
    """

    release_decision = _derive_release_decision(run, policy)
    score_display = _score_display(run, score)
    decision_label = RELEASE_DECISION_LABEL[release_decision]

    blocking = sorted(
        (f for f in findings if f.severity in {"critical", "high"}),
        key=lambda f: (SEVERITY_ORDER.index(f.severity), f.id),
    )

    blocks: list[dict[str, Any]] = []
    blocks.append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"SentinelQA — {decision_label}",
                "emoji": False,
            },
        }
    )
    blocks.append(
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Run id:* `{run.id}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Status:* `{run.status}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Score:* {score_display}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Decision:* {decision_label}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Target:* `{run.target.base_url}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Mode:* `{run.target.mode}`",
                },
            ],
        }
    )

    if blocking:
        blocks.append({"type": "divider"})
        top = blocking[:_TOP_BLOCKER_LIMIT]
        lines = ["*Top blockers*"]
        for f in top:
            lines.append(f"• [{SEVERITY_LABEL[f.severity]}] `{f.module}` — {f.title}")
        if len(blocking) > _TOP_BLOCKER_LIMIT:
            lines.append(f"_+{len(blocking) - _TOP_BLOCKER_LIMIT} more in the report._")
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(lines),
                },
            }
        )

    counts = _severity_counts(findings)
    counts_summary = ", ".join(
        f"{counts[s]} {SEVERITY_LABEL[s].lower()}" for s in SEVERITY_ORDER if counts.get(s, 0) > 0
    )
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Findings: {counts_summary or '0 findings'}",
                }
            ],
        }
    )

    if artifact_url:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Open report"},
                        "url": artifact_url,
                        "action_id": "sentinelqa_open_report",
                    }
                ],
            }
        )

    fallback = (
        f"SentinelQA {decision_label} for {run.id}; score {score_display}; "
        f"{counts_summary or '0 findings'}."
    )
    return {"text": fallback, "blocks": blocks}


def write_slack_payload(
    artifact_dir_path: Path,
    payload: Mapping[str, Any],
    *,
    filename: str = "slack-summary.json",
) -> Path:
    """Persist ``payload`` to a file. Deterministic JSON (sorted, indented)."""

    target = artifact_dir_path / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return target


def load_block_kit_schema() -> dict[str, Any]:
    """Load the vendored Block Kit subset schema."""

    payload: dict[str, Any] = json.loads(SLACK_PAYLOAD_SCHEMA_PATH.read_text(encoding="utf-8"))
    return payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_release_decision(run: TestRun, policy: PolicyDecision | None) -> ReleaseDecision:
    if policy is not None:
        return policy.release_decision
    if run.status == "unsafe_blocked":
        return "unsafe_target_rejected"
    if run.status == "dry_run":
        return "inconclusive"
    if run.status == "passed":
        return "pass"
    if run.status == "failed":
        return "blocked"
    return "inconclusive"


def _score_display(run: TestRun, score: QualityScore | None) -> str:
    if score is None or run.status in {"unsafe_blocked", "dry_run"}:
        return "n/a"
    return f"{round(float(score.total), 2)} / 100"


def _severity_counts(findings: Sequence[Finding]) -> dict[Severity, int]:
    counts: dict[Severity, int] = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


__all__ = [
    "SLACK_PAYLOAD_SCHEMA_PATH",
    "load_block_kit_schema",
    "render_slack_payload",
    "write_slack_payload",
]
