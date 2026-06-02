# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the weekly email-digest integration."""

from __future__ import annotations

import json
from email.message import EmailMessage
from pathlib import Path

import pytest
from integrations.email import (
    DigestEmail,
    DigestError,
    SmtpConfig,
    build_digest,
    render_html_digest,
    render_text_digest,
    send_digest,
)


def _write_run(
    parent: Path,
    *,
    run_id: str,
    quality: float = 90.0,
    findings: list[dict] | None = None,
) -> None:
    run_dir = parent / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "passed",
                "quality_score": quality,
                "modules_run": ["security"],
                "target": {"base_url": "https://app.example.com", "host": "app.example.com"},
                "started_at": "2026-06-01T00:00:00+00:00",
                "finished_at": "2026-06-01T00:01:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "findings.json").write_text(
        json.dumps({"findings": findings or []}), encoding="utf-8"
    )
    (run_dir / "score.json").write_text("{}", encoding="utf-8")


def _f(severity: str = "medium", title: str = "CSP missing") -> dict:
    return {
        "id": "FND-XAAAAAAAAAAA",
        "module": "security",
        "category": "headers",
        "severity": severity,
        "title": title,
        "evidence": {"rule_id": "SEC-HEADERS-CSP-MISSING"},
    }


def test_build_digest_raises_when_runs_root_empty(tmp_path: Path) -> None:
    with pytest.raises(DigestError):
        build_digest(tmp_path / "runs")


def test_build_digest_with_single_run_succeeds(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA", findings=[_f()])
    summary = build_digest(tmp_path, project_name="Demo")
    assert summary.project_name == "Demo"
    assert summary.latest_run_id == "RUN-XAAAAAAAAAAA"


def test_build_digest_diff_picks_window_start(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA", findings=[_f(severity="high")])
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAB", quality=70.0, findings=[])
    summary = build_digest(tmp_path)
    assert summary.score_delta == -20.0
    assert len(summary.resolved_findings) == 1


def test_render_text_digest_includes_score_and_findings(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA", findings=[])
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAB", findings=[_f(severity="high")])
    summary = build_digest(tmp_path)
    body = render_text_digest(summary)
    assert "Top regressions" in body
    assert "Top improvements" in body
    assert "CSP missing" in body


def test_render_html_digest_escapes_user_content(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA", findings=[])
    _write_run(
        tmp_path,
        run_id="RUN-XAAAAAAAAAAB",
        findings=[_f(severity="high", title="<script>x</script>")],
    )
    summary = build_digest(tmp_path)
    html = render_html_digest(summary)
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_send_digest_invokes_transport(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA")
    summary = build_digest(tmp_path)
    captured: dict[str, object] = {}

    def fake(_config: SmtpConfig, message: EmailMessage) -> None:
        captured["subject"] = message["Subject"]
        captured["body"] = message.get_body(("plain",)).get_content()  # type: ignore[union-attr]

    digest = send_digest(
        summary,
        sender="ci@example.com",
        recipients=("dev@example.com",),
        smtp=SmtpConfig(host="smtp.example.com"),
        transport=fake,
    )
    assert isinstance(digest, DigestEmail)
    assert "SentinelQA" in str(captured["subject"])
    assert "Latest run" in str(captured["body"])


def test_send_digest_rejects_empty_recipients(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA")
    summary = build_digest(tmp_path)
    with pytest.raises(DigestError):
        send_digest(
            summary,
            sender="ci@example.com",
            recipients=(),
            smtp=SmtpConfig(host="smtp.example.com"),
            transport=lambda *_a: None,
        )


def test_send_digest_rejects_bad_sender(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA")
    summary = build_digest(tmp_path)
    with pytest.raises(DigestError):
        send_digest(
            summary,
            sender="not-an-email",
            recipients=("dev@example.com",),
            smtp=SmtpConfig(host="smtp.example.com"),
            transport=lambda *_a: None,
        )


def test_send_digest_wraps_transport_errors(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA")
    summary = build_digest(tmp_path)

    def fake(*_a: object) -> None:
        raise OSError("smtp connection refused")

    with pytest.raises(DigestError):
        send_digest(
            summary,
            sender="ci@example.com",
            recipients=("dev@example.com",),
            smtp=SmtpConfig(host="smtp.example.com"),
            transport=fake,
        )


def test_main_dry_run_prints_subject(tmp_path: Path, capsys) -> None:
    from integrations.email.digest import main

    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA")
    rc = main(
        [
            "--runs-root",
            str(tmp_path),
            "--from",
            "ci@example.com",
            "--to",
            "dev@example.com",
            "--dry-run",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr().out
    assert "[SentinelQA]" in captured


def test_main_requires_smtp_host_when_not_dry_run(tmp_path: Path) -> None:
    from integrations.email.digest import main

    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA")
    rc = main(
        [
            "--runs-root",
            str(tmp_path),
            "--from",
            "ci@example.com",
            "--to",
            "dev@example.com",
        ]
    )
    assert rc == 2
