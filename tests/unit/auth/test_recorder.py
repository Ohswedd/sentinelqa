# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the auth-flow recorder."""

from __future__ import annotations

from pathlib import Path

from engine.auth.recorder import (
    AuthProfileDraft,
    PostCondition,
    RecordedSession,
    RecordedStep,
    build_assertion_prompt,
    codegen_command,
    parse_assertion_response,
    parse_codegen_transcript,
    record_auth_flow,
    render_profile_yaml,
    write_profile_yaml,
)


def test_codegen_command_returns_canonical_argv() -> None:
    argv = codegen_command("https://app.example.com/login")
    assert argv[0] == "playwright"
    assert "codegen" in argv
    assert "https://app.example.com/login" in argv
    assert "--browser" in argv


def test_codegen_command_respects_browser_arg() -> None:
    argv = codegen_command("https://app.example.com", browser="firefox")
    assert "firefox" in argv


def test_parse_codegen_transcript_returns_steps() -> None:
    blob = (
        '{"action":"goto","url":"https://app.example.com/login"}\n'
        '{"action":"fill","selector":"#email","value":"alice@example.com"}\n'
        '{"action":"click","selector":"button[type=submit]"}\n'
    )
    session = parse_codegen_transcript(blob, start_url="https://app.example.com/login")
    assert len(session.steps) == 3
    assert session.steps[1].selector == "#email"
    assert session.steps[2].action == "click"


def test_parse_codegen_transcript_ignores_unknown_actions() -> None:
    blob = '{"action":"sneeze","selector":"x"}\n{"action":"click","selector":"a"}\n'
    session = parse_codegen_transcript(blob, start_url="https://x")
    assert len(session.steps) == 1
    assert session.steps[0].action == "click"


def test_build_assertion_prompt_contains_step_summary() -> None:
    session = RecordedSession(
        start_url="https://app.example.com/login",
        final_url="https://app.example.com/dashboard",
        steps=(RecordedStep(action="goto", url="https://app.example.com/login"),),
    )
    prompt = build_assertion_prompt(session)
    assert "app.example.com" in prompt
    assert "ONLY the JSON array" in prompt


def test_parse_assertion_response_decodes_fenced_json() -> None:
    raw = (
        "```json\n"
        "[\n"
        '  {"kind": "selector", "value": "[data-testid=\'user-menu\']", '
        '"rationale": "Visible after login."},\n'
        '  {"kind": "url_pattern", "value": "/dashboard", '
        '"rationale": "Lands on the dashboard."}\n'
        "]\n"
        "```"
    )
    conditions = parse_assertion_response(raw)
    assert len(conditions) == 2
    assert conditions[0].kind == "selector"
    assert conditions[1].value == "/dashboard"


def test_parse_assertion_response_drops_invalid_kinds() -> None:
    raw = '[{"kind": "bogus", "value": "x"}]'
    assert parse_assertion_response(raw) == ()


def test_parse_assertion_response_caps_at_five() -> None:
    rows = [f'{{"kind": "selector", "value": "#sel-{i}"}}' for i in range(10)]
    raw = "[" + ", ".join(rows) + "]"
    assert len(parse_assertion_response(raw)) == 5


def test_render_profile_yaml_includes_required_fields() -> None:
    draft = AuthProfileDraft(
        name="example",
        label="Example Login",
        login_url_pattern="https://app.example.com/login",
        success_url_patterns=("https://app.example.com/dashboard",),
        steps=(
            RecordedStep(action="goto", url="https://app.example.com/login"),
            RecordedStep(action="fill", selector="#email", value="alice@x.com"),
            RecordedStep(action="click", selector="button[type=submit]"),
        ),
        post_conditions=(
            PostCondition(
                kind="selector",
                value="[data-testid='user-menu']",
                rationale="Visible after login.",
            ),
        ),
    )
    yaml_text = render_profile_yaml(draft)
    assert "name: example" in yaml_text
    assert "login_url_pattern:" in yaml_text
    assert "post_conditions:" in yaml_text
    assert "user-menu" in yaml_text


def test_record_auth_flow_calls_codegen_runner() -> None:
    captured: dict[str, object] = {}

    def runner(url: str, _opts: dict) -> RecordedSession:
        captured["url"] = url
        return RecordedSession(
            start_url=url,
            final_url="https://app.example.com/dashboard",
            steps=(RecordedStep(action="click", selector="#login"),),
        )

    draft = record_auth_flow(
        start_url="https://app.example.com/login",
        profile_name="local",
        profile_label="Local Login",
        codegen_runner=runner,
    )
    assert captured["url"] == "https://app.example.com/login"
    assert draft.success_url_patterns == ("https://app.example.com/dashboard",)
    assert draft.steps[0].selector == "#login"


def test_record_auth_flow_uses_assertion_adapter() -> None:
    def runner(url: str, _opts: dict) -> RecordedSession:
        return RecordedSession(
            start_url=url,
            final_url="https://app.example.com/dashboard",
            steps=(),
        )

    def adapter(_system, _user, _model):
        return (
            '[{"kind": "selector", "value": "#avatar", "rationale": "Avatar appears."}]',
            True,
            "",
        )

    draft = record_auth_flow(
        start_url="https://app.example.com/login",
        profile_name="local",
        profile_label="Local Login",
        codegen_runner=runner,
        assertion_adapter=adapter,
    )
    assert len(draft.post_conditions) == 1
    assert draft.post_conditions[0].value == "#avatar"


def test_record_auth_flow_handles_adapter_failure() -> None:
    def runner(url: str, _opts: dict) -> RecordedSession:
        return RecordedSession(start_url=url, final_url="x", steps=())

    def adapter(*_a, **_k):
        raise RuntimeError("LLM down")

    draft = record_auth_flow(
        start_url="https://x",
        profile_name="x",
        profile_label="x",
        codegen_runner=runner,
        assertion_adapter=adapter,
    )
    assert draft.post_conditions == ()


def test_write_profile_yaml_creates_file(tmp_path: Path) -> None:
    draft = AuthProfileDraft(
        name="x",
        label="X",
        login_url_pattern="https://x",
        success_url_patterns=(),
        steps=(),
    )
    target = tmp_path / "profile.yaml"
    write_profile_yaml(draft, path=target)
    assert target.is_file()
    body = target.read_text(encoding="utf-8")
    assert "name: x" in body
