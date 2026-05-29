"""Helper-level coverage for modules.llm_audit (Phase 19.15).

Targets the defensive branches in :mod:`modules.llm_audit.inputs`,
:mod:`modules.llm_audit.findings`, and the less-common credential
patterns in :mod:`modules.llm_audit.checks.hardcoded_creds`. The
broken-fixture sweep covers the happy paths; these tests round out
the per-file coverage floor (≥ 90 %).
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.domain.ids import IdGenerator

from modules.llm_audit.checks.hardcoded_creds import check_hardcoded_credentials
from modules.llm_audit.findings import CheckFinding, findings_from_check_findings
from modules.llm_audit.inputs import load_inputs
from modules.llm_audit.models import SourceFile

# ---------------------------------------------------------------------------
# inputs.py — malformed / missing payloads
# ---------------------------------------------------------------------------


def test_load_inputs_with_no_paths_returns_empty(tmp_path: Path) -> None:
    inputs = load_inputs(discovery_path=None, signals_root=None)
    assert inputs.link_references == ()
    assert inputs.api_references == ()
    assert inputs.buttons == ()
    assert inputs.forms == ()
    assert inputs.observed_routes == ()


def test_load_inputs_with_missing_files(tmp_path: Path) -> None:
    inputs = load_inputs(
        discovery_path=tmp_path / "missing.json",
        signals_root=tmp_path / "nope",
    )
    assert inputs.link_references == ()


def test_load_inputs_handles_malformed_json(tmp_path: Path) -> None:
    bad = tmp_path / "discovery.json"
    bad.write_text("not json {{", encoding="utf-8")
    inputs = load_inputs(discovery_path=bad, signals_root=None)
    assert inputs.link_references == ()


def test_load_inputs_rejects_non_mapping_json(tmp_path: Path) -> None:
    array_root = tmp_path / "discovery.json"
    array_root.write_text("[1, 2, 3]", encoding="utf-8")
    inputs = load_inputs(discovery_path=array_root, signals_root=None)
    assert inputs.link_references == ()


def test_load_inputs_with_partial_payloads(tmp_path: Path) -> None:
    discovery = tmp_path / "discovery.json"
    discovery.write_text(
        json.dumps(
            {
                "crawl": "not-a-mapping",  # forces the non-mapping branch
            }
        ),
        encoding="utf-8",
    )
    inputs = load_inputs(discovery_path=discovery, signals_root=None)
    assert inputs.link_references == ()


def test_load_inputs_skips_invalid_entries(tmp_path: Path) -> None:
    signals_root = tmp_path / "signals"
    signals_root.mkdir()
    (signals_root / "signals.json").write_text(
        json.dumps(
            {
                "buttons": [
                    {"selector": "missing-route"},
                    "not a mapping",
                    {"route_url": "/", "selector": "btn", "label": "Go"},
                ],
                "rendered_text": [
                    {"text": "no route"},
                    {"route_url": "/x", "text": ""},
                    {
                        "route_url": "/x",
                        "text": "lorem ipsum dolor",
                        "is_authenticated_flow": False,
                    },
                ],
                "resources": ["not a mapping", {"resource": ""}],
                "auth_route_probes": [
                    {"route_path": ""},
                    {"route_path": "/admin", "backend_status_code": "not-an-int"},
                ],
                "storage_samples": [
                    {"route_url": "/", "store": "local", "entries": "not-a-mapping"},
                    {"route_url": "/", "store": "local", "entries": {"k": "v"}},
                ],
                "loading_error_observations": ["bogus"],
                "validation_probes": ["bogus"],
                "console_entries": ["bogus"],
                "bundles": ["bogus", {"path": ""}],
                "form_exercises": "not-a-mapping",
            }
        ),
        encoding="utf-8",
    )
    inputs = load_inputs(
        discovery_path=None,
        signals_root=signals_root,
    )
    assert len(inputs.buttons) == 1
    assert inputs.buttons[0].label == "Go"
    assert len(inputs.rendered_text) == 1
    assert inputs.resources == ()
    assert len(inputs.storage_samples) == 1
    assert inputs.loading_error_observations == ()


def test_load_inputs_with_non_list_signal_section(tmp_path: Path) -> None:
    signals_root = tmp_path / "signals"
    signals_root.mkdir()
    (signals_root / "signals.json").write_text(
        json.dumps({"buttons": "not a list", "console_entries": "nope"}),
        encoding="utf-8",
    )
    inputs = load_inputs(discovery_path=None, signals_root=signals_root)
    assert inputs.buttons == ()
    assert inputs.console_entries == ()


def test_load_inputs_discovery_pages_skip_blank_url(tmp_path: Path) -> None:
    discovery = tmp_path / "discovery.json"
    discovery.write_text(
        json.dumps(
            {
                "crawl": {
                    "pages": [
                        "not a mapping",
                        {"url": ""},
                        {
                            "url": "http://localhost/",
                            "status_code": 200,
                            "discovered_links": "not a list",
                        },
                        {"url": "http://localhost/x", "status_code": "nope"},
                        {
                            "url": "http://localhost/y",
                            "status_code": 200,
                            "discovered_links": [1, "/a", None],
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    inputs = load_inputs(discovery_path=discovery, signals_root=None)
    assert "http://localhost/" in inputs.observed_routes
    assert "http://localhost/y" in inputs.observed_routes
    assert any(ref.target_path == "/a" for ref in inputs.link_references)


def test_load_inputs_api_endpoints_skip_invalid(tmp_path: Path) -> None:
    discovery = tmp_path / "discovery.json"
    discovery.write_text(json.dumps({}), encoding="utf-8")
    (tmp_path / "api.json").write_text(
        json.dumps(
            {
                "endpoints": [
                    "bogus",
                    {"method": "GET"},
                    {"path": ""},
                    {"method": "GET", "path": "/api/x"},
                ],
                "referenced_only_paths": [1, "/api/imag", ""],
                "openapi": {"expected_but_not_observed": [1, "/api/doc", ""]},
            }
        ),
        encoding="utf-8",
    )
    inputs = load_inputs(discovery_path=discovery, signals_root=None)
    assert ("GET", "/api/x") in inputs.observed_endpoints
    assert any(r.path == "/api/imag" for r in inputs.api_references)
    assert ("GET", "/api/doc") in inputs.openapi_endpoints


def test_load_inputs_forms_with_exercise_signal(tmp_path: Path) -> None:
    discovery = tmp_path / "discovery.json"
    discovery.write_text(json.dumps({}), encoding="utf-8")
    (tmp_path / "forms.json").write_text(
        json.dumps(
            {
                "forms": [
                    "bogus",
                    {"id": "", "route_url": "/x"},
                    {
                        "id": "FRM-AAAAAAAABBBB",
                        "route_url": "/x",
                        "action_url": "/api/x",
                        "method": "POST",
                        "submit_handler_present": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    signals_root = tmp_path / "signals"
    signals_root.mkdir()
    (signals_root / "signals.json").write_text(
        json.dumps(
            {
                "form_exercises": {
                    "FRM-AAAAAAAABBBB": {
                        "exercised": True,
                        "produced_network_request": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    inputs = load_inputs(discovery_path=discovery, signals_root=signals_root)
    assert len(inputs.forms) == 1
    assert inputs.forms[0].was_exercised is True
    assert inputs.forms[0].produced_network_request is True


def test_load_inputs_source_files_skips_blank_paths(tmp_path: Path) -> None:
    signals_root = tmp_path / "signals"
    signals_root.mkdir()
    (signals_root / "source_files.json").write_text(
        json.dumps(
            {
                "source_files": [
                    {"path": "", "body": "x"},
                    {"path": "src/a.js", "body": ""},
                    {"path": "src/b.js", "body": "const x = 1;"},
                    "bogus",
                ]
            }
        ),
        encoding="utf-8",
    )
    inputs = load_inputs(discovery_path=None, signals_root=signals_root)
    assert len(inputs.source_files) == 1
    assert inputs.source_files[0].path == "src/b.js"


# ---------------------------------------------------------------------------
# findings.py — description shaping, snippet clipping, evidence fallback
# ---------------------------------------------------------------------------


def test_findings_from_check_findings_uses_fallback_evidence() -> None:
    cf = CheckFinding(
        rule_id="LLM-DEAD-BTN",
        title="Sample",
        description="d",
        route="/",
    )
    findings = findings_from_check_findings(
        [cf],
        run_id="RUN-AAAAAAAAAAAA",
        module_name="llm_audit",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
    )
    assert findings[0].evidence
    assert str(findings[0].evidence[0].path) == "llm_audit/index.json"


def test_findings_truncate_long_snippets() -> None:
    long_snippet = "x" * 2000
    cf = CheckFinding(
        rule_id="LLM-DEAD-BTN",
        title="Sample",
        description="d",
        snippet=long_snippet,
    )
    findings = findings_from_check_findings(
        [cf],
        run_id="RUN-AAAAAAAAAAAA",
        module_name="llm_audit",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
    )
    desc = findings[0].description
    # 800-char clip plus ellipsis is the snippet's contribution.
    assert "…" in desc
    assert "Observed:" in desc


def test_findings_emit_extra_context() -> None:
    cf = CheckFinding(
        rule_id="LLM-DEAD-BTN",
        title="Sample",
        description="d",
        extra_context=(("k1", "v1"), ("k2", "v2")),
    )
    findings = findings_from_check_findings(
        [cf],
        run_id="RUN-AAAAAAAAAAAA",
        module_name="llm_audit",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
    )
    assert "- k1: v1" in findings[0].description
    assert "- k2: v2" in findings[0].description


def test_findings_evidence_path_classifier() -> None:
    cf = CheckFinding(
        rule_id="LLM-DEAD-BTN",
        title="Sample",
        description="d",
        evidence_paths=(
            "shot.png",
            "trace.zip",
            "har.har",
            "snap.html",
            "log.txt",
            "video.webm",
            "other.bin",
        ),
    )
    findings = findings_from_check_findings(
        [cf],
        run_id="RUN-AAAAAAAAAAAA",
        module_name="llm_audit",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
    )
    types = {ev.type for ev in findings[0].evidence}
    assert {
        "screenshot",
        "trace",
        "har",
        "dom_snapshot",
        "console_log",
        "video",
        "source_ref",
    } <= types


def test_findings_long_description_truncated() -> None:
    cf = CheckFinding(
        rule_id="LLM-DEAD-BTN",
        title="Sample",
        description="x" * 10_000,
    )
    findings = findings_from_check_findings(
        [cf],
        run_id="RUN-AAAAAAAAAAAA",
        module_name="llm_audit",
        target_base_url="http://localhost",
        id_generator=IdGenerator(),
    )
    assert len(findings[0].description) <= 8000


# ---------------------------------------------------------------------------
# hardcoded_creds.py — exercise remaining patterns
# ---------------------------------------------------------------------------


def test_aws_access_key_pattern() -> None:
    src = SourceFile(
        path="src/aws.js",
        body="const id = 'AKIAIOSFODNN7EXAMPLE';\n",
    )
    findings = check_hardcoded_credentials([src])
    assert any(f.rule_id == "LLM-HARDCODED-CRED" for f in findings)


def test_openai_key_pattern() -> None:
    src = SourceFile(
        path="src/ai.js",
        body="const k = 'sk-AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIII';\n",
    )
    findings = check_hardcoded_credentials([src])
    assert any(f.rule_id == "LLM-HARDCODED-CRED" for f in findings)


def test_stripe_secret_pattern() -> None:
    src = SourceFile(
        path="src/billing.js",
        body="const k = 'sk_live_AAAAAAAAAAAAAAAAAAAA';\n",
    )
    findings = check_hardcoded_credentials([src])
    assert any(f.rule_id == "LLM-HARDCODED-CRED" for f in findings)


def test_password_constant_pattern() -> None:
    src = SourceFile(
        path="src/seed.js",
        body="export const DEMO_PASSWORD = 'demo123!';\n",
    )
    findings = check_hardcoded_credentials([src])
    assert any(f.rule_id == "LLM-HARDCODED-CRED" for f in findings)


def test_auth_token_assignment_pattern() -> None:
    src = SourceFile(
        path="src/client.js",
        body="const api_key = 'a1b2c3d4e5f6g7h8i9j0';\n",
    )
    findings = check_hardcoded_credentials([src])
    assert any(f.rule_id == "LLM-HARDCODED-CRED" for f in findings)


def test_overlong_line_redaction_window_clipped() -> None:
    padding = "x" * 260
    src = SourceFile(
        path="src/long.js",
        body=(f"const DEMO_PASSWORD = 'short-secret-A'; // {padding}\n"),
    )
    findings = check_hardcoded_credentials([src])
    assert findings
    for f in findings:
        assert f.snippet
        # Snippet hard-clipped to 240 chars + ellipsis.
        assert len(f.snippet) <= 241
        assert f.snippet.endswith("…")


def test_finditer_matches_two_lines() -> None:
    src = SourceFile(
        path="src/multi.js",
        body=(
            "const DEMO_PASSWORD = 'first-secret-A';\n"
            "const ADMIN_PASSWORD = 'second-secret-B';\n"
        ),
    )
    findings = check_hardcoded_credentials([src])
    lines = {f.line for f in findings if f.line is not None}
    assert lines >= {1, 2}


def test_normalize_path_strips_scheme() -> None:
    from modules.llm_audit.checks.fake_routes import _normalize_path

    # 'http://' inside the path segment exercises the schemed-path branch.
    assert _normalize_path("relative/path") == "/relative/path"
    # Trailing slash on root stays "/" (single slash).
    assert _normalize_path("//") == "/"


def test_check_fake_routes_skips_prefix_match() -> None:
    from modules.llm_audit.checks.fake_routes import check_fake_routes
    from modules.llm_audit.models import LinkReference

    # Target /api is a parent of observed /api/users — no finding.
    findings = check_fake_routes(
        [LinkReference(source_route="/", target_path="/api")],
        observed_routes=["/api/users"],
        observed_route_status={"/api/users": 200},
    )
    assert findings == ()


def test_check_console_logs_dropped_when_third_party_only() -> None:
    from modules.llm_audit.checks.console_errors import check_console_errors
    from modules.llm_audit.models import ConsoleEntry

    findings = check_console_errors(
        [
            ConsoleEntry(
                route_url="http://localhost/",
                level="error",
                text="just an error",
                ui_reported_success=True,
                source_url="https://analytics.example.com/x",
            )
        ],
        third_party_hosts=["example.com"],
    )
    assert findings == ()


def test_check_console_log_level_not_error_ignored() -> None:
    from modules.llm_audit.checks.console_errors import check_console_errors
    from modules.llm_audit.models import ConsoleEntry

    findings = check_console_errors(
        [
            ConsoleEntry(
                route_url="http://localhost/",
                level="warn",
                text="a warning",
                ui_reported_success=True,
            )
        ]
    )
    assert findings == ()


def test_console_third_party_filter_with_unhandled_rejection() -> None:
    from modules.llm_audit.checks.console_errors import check_console_errors
    from modules.llm_audit.models import ConsoleEntry

    entry = ConsoleEntry(
        route_url="http://localhost/",
        level="error",
        text="rejection",
        is_unhandled_rejection=True,
        source_url="https://analytics.example.com/beacon",
    )
    findings = check_console_errors([entry], third_party_hosts=["example.com"])
    assert findings == ()


def test_module_summarize_no_signal_means_skipped(tmp_path: Path) -> None:
    """`summarize` rolls up to ``skipped`` when no signals were available."""
    from datetime import UTC, datetime

    from engine.config.loader import load_config
    from engine.domain.target import Target
    from engine.modules.base import ModuleContext
    from engine.orchestrator.artifacts import ArtifactDirectory
    from engine.policy.safety import SafetyDecision

    from modules.llm_audit import LlmAuditModule

    cfg_path = tmp_path / "sentinel.config.yaml"
    cfg_path.write_text(
        "version: 1\n"
        "project:\n  name: x\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    artifacts_root = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    target = Target(
        base_url=cfg.target.base_url,
        allowed_hosts=frozenset(cfg.target.allowed_hosts),
        mode="safe",
    )
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="test",
        decided_at=datetime.now(UTC),
    )
    ctx = ModuleContext(
        module_name="llm_audit",
        config=cfg,
        safety_decision=safety,
        artifacts=ArtifactDirectory(artifacts_root),
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=artifacts_root,
        target=target,
        id_generator=IdGenerator(),
        options={},
    )
    module = LlmAuditModule(cfg, safety)
    result = module.run(ctx)
    assert result.status == "skipped"
    assert result.findings == ()
