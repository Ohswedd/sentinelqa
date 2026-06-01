# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""LLM-assisted authentication-flow recorder (v1.4.0).

The auth-profile YAML today has to be hand-written. The recorder
wraps Playwright's ``codegen`` so the user just clicks through the
flow, then optionally asks an LLM to propose post-condition
assertions (e.g. "after login the page should contain
``[data-testid='user-menu']``").

The module is pure / I/O free at the seams: a stub codegen runner
returns a synthetic transcript, a stub assertion-suggester returns
canned suggestions, and the writer produces YAML to a tmp_path.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PostConditionKind = Literal["url_pattern", "selector", "text_contains", "cookie_present"]


@dataclass(frozen=True, slots=True)
class RecordedStep:
    """One step captured by ``playwright codegen``."""

    action: Literal["goto", "fill", "click", "press", "select_option"]
    selector: str = ""
    value: str = ""
    url: str = ""


@dataclass(frozen=True, slots=True)
class RecordedSession:
    """The transcript ``playwright codegen`` produced."""

    start_url: str
    steps: tuple[RecordedStep, ...]
    final_url: str = ""
    title: str = ""


@dataclass(frozen=True, slots=True)
class PostCondition:
    """One assertion the recorder will write into the profile."""

    kind: PostConditionKind
    value: str
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class AuthProfileDraft:
    """The profile YAML the recorder will emit."""

    name: str
    label: str
    login_url_pattern: str
    success_url_patterns: tuple[str, ...]
    steps: tuple[RecordedStep, ...]
    post_conditions: tuple[PostCondition, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# Codegen invocation seam
# --------------------------------------------------------------------------- #


CodegenRunner = Callable[[str, dict[str, Any]], RecordedSession]


def codegen_command(start_url: str, *, browser: str = "chromium") -> tuple[str, ...]:
    """Return the argv for ``playwright codegen``.

    Kept as a pure function so tests can assert on the exact
    invocation without spawning a real Playwright session.
    """

    return (
        "playwright",
        "codegen",
        "--browser",
        browser,
        "--target",
        "json",
        start_url,
    )


# --------------------------------------------------------------------------- #
# Transcript parsing
# --------------------------------------------------------------------------- #

# Match Playwright codegen's standard JSON transcript lines:
#   { "action": "click", "selector": "...", "url": "..." }
# The real codegen emits JS code by default; we use the ``--target json``
# flag which produces a one-step-per-line transcript.
_TRANSCRIPT_LINE_RE = re.compile(r'^\s*\{\s*"action"\s*:\s*"([a-z_]+)"')


def parse_codegen_transcript(blob: str, *, start_url: str) -> RecordedSession:
    """Best-effort transcript parser."""

    import json

    steps: list[RecordedStep] = []
    final_url = start_url
    title = ""
    for line in blob.splitlines():
        if not _TRANSCRIPT_LINE_RE.match(line):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        action = payload.get("action")
        if action not in {"goto", "fill", "click", "press", "select_option"}:
            continue
        steps.append(
            RecordedStep(
                action=action,
                selector=str(payload.get("selector", "")),
                value=str(payload.get("value", "")),
                url=str(payload.get("url", "")),
            )
        )
        if action == "goto":
            final_url = str(payload.get("url", final_url))
    return RecordedSession(
        start_url=start_url,
        steps=tuple(steps),
        final_url=final_url,
        title=title,
    )


# --------------------------------------------------------------------------- #
# LLM post-condition suggester
# --------------------------------------------------------------------------- #


def build_assertion_prompt(session: RecordedSession) -> str:
    """Return the locked user prompt for the assertion suggester."""

    import json

    payload = {
        "start_url": session.start_url,
        "final_url": session.final_url,
        "step_summary": [
            {
                "action": s.action,
                "selector": s.selector,
                "url": s.url,
            }
            for s in session.steps
        ],
    }
    return (
        "A user just walked through an authentication flow. Propose 1-3 "
        "post-condition assertions SentinelQA can use to verify the "
        "session is logged in. Output a JSON array of objects with "
        "`kind` (url_pattern, selector, text_contains, cookie_present), "
        "`value` (the literal selector / pattern), and `rationale` (one "
        "sentence). The flow transcript is:\n\n"
        "```json\n"
        f"{json.dumps(payload, sort_keys=True, indent=2)}\n"
        "```\n"
        "Output ONLY the JSON array."
    )


def parse_assertion_response(raw: str) -> tuple[PostCondition, ...]:
    """Parse the model output into validated :class:`PostCondition` rows."""

    import json

    text = raw.strip()
    if text.startswith("```"):
        # Drop fenced wrapping.
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
    try:
        rows = json.loads(text)
    except json.JSONDecodeError:
        return ()
    if not isinstance(rows, list):
        return ()
    out: list[PostCondition] = []
    valid_kinds = {"url_pattern", "selector", "text_contains", "cookie_present"}
    for row in rows[:5]:  # cap at 5
        if not isinstance(row, dict):
            continue
        kind = row.get("kind")
        value = row.get("value")
        if (
            kind not in valid_kinds
            or not isinstance(value, str)
            or not value.strip()
            or not isinstance(kind, str)
        ):
            continue
        out.append(
            PostCondition(
                kind=kind,
                value=value.strip(),
                rationale=str(row.get("rationale", ""))[:280],
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------- #
# Profile draft → YAML
# --------------------------------------------------------------------------- #


def render_profile_yaml(draft: AuthProfileDraft) -> str:
    """Render the draft as the auth-profile YAML the loader expects."""

    lines: list[str] = [
        "# Generated by `sentinel auth record` — review before committing.",
        f"name: {draft.name}",
        f"label: {draft.label!r}",
        f"login_url_pattern: {draft.login_url_pattern!r}",
        "success_url_patterns:",
    ]
    for pattern in draft.success_url_patterns:
        lines.append(f"  - {pattern!r}")
    lines.append("steps:")
    for step in draft.steps:
        lines.append(f"  - action: {step.action}")
        if step.selector:
            lines.append(f"    selector: {step.selector!r}")
        if step.value:
            lines.append(f"    value: {step.value!r}")
        if step.url:
            lines.append(f"    url: {step.url!r}")
    if draft.post_conditions:
        lines.append("post_conditions:")
        for pc in draft.post_conditions:
            lines.append(f"  - kind: {pc.kind}")
            lines.append(f"    value: {pc.value!r}")
            if pc.rationale:
                lines.append(f"    rationale: {pc.rationale!r}")
    return "\n".join(lines) + "\n"


def record_auth_flow(
    *,
    start_url: str,
    profile_name: str,
    profile_label: str,
    codegen_runner: CodegenRunner,
    assertion_adapter: object | None = None,
) -> AuthProfileDraft:
    """Orchestrate the recording.

    The CLI passes in a codegen runner that invokes Playwright; tests
    pass a stub returning a canned :class:`RecordedSession`. The
    optional LLM ``assertion_adapter`` is a callable
    ``(system, user, model) -> (text, available, detail)``.
    """

    session = codegen_runner(start_url, {})
    post_conditions: tuple[PostCondition, ...] = ()
    if assertion_adapter is not None:
        prompt = build_assertion_prompt(session)
        try:
            text, available, _detail = assertion_adapter(  # type: ignore[operator]
                "You propose post-condition assertions for auth flows.",
                prompt,
                "claude-3-5-sonnet-latest",
            )
        except Exception:
            text, available = "", False
        if available and text:
            post_conditions = parse_assertion_response(text)

    return AuthProfileDraft(
        name=profile_name,
        label=profile_label,
        login_url_pattern=start_url,
        success_url_patterns=(session.final_url,) if session.final_url else (),
        steps=session.steps,
        post_conditions=post_conditions,
    )


def write_profile_yaml(draft: AuthProfileDraft, *, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_profile_yaml(draft), encoding="utf-8")
    return path


__all__ = [
    "AuthProfileDraft",
    "CodegenRunner",
    "PostCondition",
    "RecordedSession",
    "RecordedStep",
    "build_assertion_prompt",
    "codegen_command",
    "parse_assertion_response",
    "parse_codegen_transcript",
    "record_auth_flow",
    "render_profile_yaml",
    "write_profile_yaml",
]
