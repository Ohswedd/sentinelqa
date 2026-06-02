# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Weekly email digest.

Walks a runs directory, picks the run from the start of the
configured window and the latest run, diffs them, and produces a
plain-text + HTML email body summarising:

* the current run's score and status,
* the top 3 regressions (new findings / severity escalations),
* the top 3 improvements (resolved findings / severity drops).

Transport is stdlib :mod:`smtplib`. The sender lives in a small
``SmtpConfig`` value object so tests can inject a fake transport.
"""

from __future__ import annotations

import argparse
import logging
import os
import smtplib
import ssl
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path
from typing import Any, Final

from engine.reporter.run_diff import compute_run_diff
from engine.runs.compare import SeverityChange
from engine.runs.summary import FindingRef

logger = logging.getLogger("sentinelqa.integrations.email")

SMTP_HOST_ENV: Final[str] = "SENTINELQA_SMTP_HOST"
SMTP_PORT_ENV: Final[str] = "SENTINELQA_SMTP_PORT"
SMTP_USERNAME_ENV: Final[str] = "SENTINELQA_SMTP_USERNAME"
SMTP_PASSWORD_ENV: Final[str] = "SENTINELQA_SMTP_PASSWORD"


class DigestError(RuntimeError):
    """Raised when the digest cannot be built or sent safely."""


@dataclass(frozen=True, slots=True)
class SmtpConfig:
    """SMTP connection details."""

    host: str
    port: int = 587
    username: str = ""
    password: str = ""
    use_starttls: bool = True
    timeout_seconds: float = 30.0


@dataclass(frozen=True, slots=True)
class DigestSummary:
    """The data the templates render."""

    project_name: str
    base_url: str
    latest_run_id: str
    latest_status: str
    latest_quality_score: float | None
    score_delta: float | None
    new_findings: tuple[FindingRef, ...] = field(default_factory=tuple)
    resolved_findings: tuple[FindingRef, ...] = field(default_factory=tuple)
    severity_regressions: tuple[SeverityChange, ...] = field(default_factory=tuple)
    severity_improvements: tuple[SeverityChange, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DigestEmail:
    """One rendered digest email."""

    subject: str
    text_body: str
    html_body: str


_TOP_N: Final[int] = 3


def _iter_run_dirs(runs_root: Path) -> tuple[Path, ...]:
    if not runs_root.is_dir():
        return ()
    return tuple(
        sorted(
            (p for p in runs_root.iterdir() if p.is_dir() and p.name.startswith("RUN-")),
            key=lambda p: p.name,
        )
    )


def _pick_window(run_dirs: Sequence[Path]) -> tuple[Path | None, Path | None]:
    """Return ``(window-start, latest)`` run dirs.

    The digest covers the last ``N`` runs; we hard-code the window
    to the last 5 runs for the "weekly" cadence. Smaller history
    falls back to the oldest available run.
    """

    if not run_dirs:
        return None, None
    if len(run_dirs) == 1:
        return run_dirs[0], run_dirs[0]
    window_start_index = max(0, len(run_dirs) - 5)
    return run_dirs[window_start_index], run_dirs[-1]


class DigestBuilder:
    """Builds a :class:`DigestSummary` from a runs directory."""

    def __init__(self, runs_root: Path, *, project_name: str = "SentinelQA") -> None:
        self.runs_root = runs_root
        self.project_name = project_name

    def build(self) -> DigestSummary:
        run_dirs = _iter_run_dirs(self.runs_root)
        window_start, latest = _pick_window(run_dirs)
        if latest is None or window_start is None:
            raise DigestError(
                f"No runs to digest under {self.runs_root}. " "Run `sentinel audit` first."
            )
        diff = compute_run_diff(window_start, latest)
        regressions = tuple(
            c for c in diff.comparison.severity_changes if c.direction == "regressed"
        )[:_TOP_N]
        improvements = tuple(
            c for c in diff.comparison.severity_changes if c.direction == "improved"
        )[:_TOP_N]
        status_after = diff.comparison.severity_counts_after.get("status", "")
        latest_status: str = (
            status_after if isinstance(status_after, str) and status_after else _status_for(latest)
        )
        return DigestSummary(
            project_name=self.project_name,
            base_url="",
            latest_run_id=diff.after_run_id,
            latest_status=latest_status,
            latest_quality_score=_score_for(latest),
            score_delta=diff.comparison.score_delta,
            new_findings=diff.comparison.new[:_TOP_N],
            resolved_findings=diff.comparison.resolved[:_TOP_N],
            severity_regressions=regressions,
            severity_improvements=improvements,
        )


def _score_for(run_dir: Path) -> float | None:
    import json as _json

    try:
        payload = _json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError):
        return None
    quality = payload.get("quality_score")
    return float(quality) if isinstance(quality, int | float) else None


def _status_for(run_dir: Path) -> str:
    import json as _json

    try:
        payload = _json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError):
        return ""
    return str(payload.get("status", ""))


def build_digest(
    runs_root: Path,
    *,
    project_name: str = "SentinelQA",
) -> DigestSummary:
    """Convenience wrapper around :class:`DigestBuilder`."""

    return DigestBuilder(runs_root, project_name=project_name).build()


# --------------------------------------------------------------------------- #
# Renderers
# --------------------------------------------------------------------------- #


def render_text_digest(summary: DigestSummary) -> str:
    """Plain-text digest body."""

    score_line = (
        f"Quality score: {summary.latest_quality_score:.1f}"
        if summary.latest_quality_score is not None
        else "Quality score: n/a"
    )
    delta_line = (
        f" ({'+' if summary.score_delta and summary.score_delta >= 0 else ''}"
        f"{summary.score_delta:.1f} since previous window)"
        if summary.score_delta is not None
        else ""
    )
    new_lines = (
        "\n".join(f"  - [{f.severity}] {f.module}: {f.title}" for f in summary.new_findings)
        or "  (none)"
    )
    resolved_lines = (
        "\n".join(f"  - [{f.severity}] {f.module}: {f.title}" for f in summary.resolved_findings)
        or "  (none)"
    )
    return (
        f"{summary.project_name} — SentinelQA weekly digest\n\n"
        f"Latest run: {summary.latest_run_id} ({summary.latest_status or 'unknown'})\n"
        f"{score_line}{delta_line}\n\n"
        "Top regressions:\n"
        f"{new_lines}\n\n"
        "Top improvements:\n"
        f"{resolved_lines}\n\n"
        "Open the SentinelQA viewer for the full report.\n"
    )


def render_html_digest(summary: DigestSummary) -> str:
    """HTML digest body — minimal, table-based for client compatibility."""

    score = (
        f"{summary.latest_quality_score:.1f}" if summary.latest_quality_score is not None else "n/a"
    )
    delta = ""
    if summary.score_delta is not None:
        direction = "▲" if summary.score_delta >= 0 else "▼"
        delta = (
            f' <span style="color:#6b7280;">' f"{direction} {abs(summary.score_delta):.1f}</span>"
        )
    new_rows = "".join(
        f"<tr><td><strong>{escape(f.severity)}</strong></td>"
        f"<td>{escape(f.module)}</td>"
        f"<td>{escape(f.title)}</td></tr>"
        for f in summary.new_findings
    )
    resolved_rows = "".join(
        f"<tr><td><strong>{escape(f.severity)}</strong></td>"
        f"<td>{escape(f.module)}</td>"
        f"<td>{escape(f.title)}</td></tr>"
        for f in summary.resolved_findings
    )
    new_block = (
        f"<h3>New findings</h3>"
        f"<table border='1' cellpadding='6' cellspacing='0'>{new_rows}</table>"
        if new_rows
        else "<h3>New findings</h3><p>None.</p>"
    )
    resolved_block = (
        f"<h3>Resolved findings</h3>"
        f"<table border='1' cellpadding='6' cellspacing='0'>{resolved_rows}</table>"
        if resolved_rows
        else "<h3>Resolved findings</h3><p>None.</p>"
    )
    return (
        f"<h1>{escape(summary.project_name)}</h1>"
        f"<p>Latest run: <code>{escape(summary.latest_run_id)}</code> "
        f"({escape(summary.latest_status or 'unknown')})</p>"
        f"<p><strong>Quality score:</strong> {score}{delta}</p>"
        f"{new_block}"
        f"{resolved_block}"
    )


def _subject_for(summary: DigestSummary) -> str:
    score = (
        f"{summary.latest_quality_score:.1f}" if summary.latest_quality_score is not None else "n/a"
    )
    return f"[SentinelQA] {summary.project_name} digest — score {score}"


def _build_email_message(
    summary: DigestSummary,
    *,
    sender: str,
    recipients: Sequence[str],
) -> tuple[EmailMessage, DigestEmail]:
    msg = EmailMessage()
    digest = DigestEmail(
        subject=_subject_for(summary),
        text_body=render_text_digest(summary),
        html_body=render_html_digest(summary),
    )
    msg["Subject"] = digest.subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(digest.text_body)
    msg.add_alternative(digest.html_body, subtype="html")
    return msg, digest


# --------------------------------------------------------------------------- #
# SMTP sender (with test seam)
# --------------------------------------------------------------------------- #


Transport = Callable[[SmtpConfig, EmailMessage], None]


def _default_transport(config: SmtpConfig, message: EmailMessage) -> None:
    if config.use_starttls:
        context = ssl.create_default_context()
        with smtplib.SMTP(config.host, config.port, timeout=config.timeout_seconds) as client:
            client.starttls(context=context)
            if config.username:
                client.login(config.username, config.password)
            client.send_message(message)
        return
    with smtplib.SMTP_SSL(config.host, config.port, timeout=config.timeout_seconds) as client:
        if config.username:
            client.login(config.username, config.password)
        client.send_message(message)


def send_digest(
    summary: DigestSummary,
    *,
    sender: str,
    recipients: Sequence[str],
    smtp: SmtpConfig,
    transport: Transport | None = None,
) -> DigestEmail:
    """Send a digest. Returns the rendered :class:`DigestEmail`.

    ``transport`` is a test seam — tests pass a callable that records
    the message instead of dialling SMTP.
    """

    if not sender or "@" not in sender:
        raise DigestError(f"sender {sender!r} is not a valid email address.")
    if not recipients:
        raise DigestError("recipients list is empty.")

    message, digest = _build_email_message(summary, sender=sender, recipients=recipients)
    handler = transport or _default_transport
    try:
        handler(smtp, message)
    except Exception as exc:
        raise DigestError(f"smtp send failed: {type(exc).__name__}: {exc}") from exc
    return digest


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sentinelqa-digest",
        description="Send a weekly SentinelQA digest email.",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path(".sentinel/runs"),
    )
    parser.add_argument("--project-name", default="SentinelQA")
    parser.add_argument("--from", dest="sender", required=True)
    parser.add_argument(
        "--to", action="append", required=True, help="repeatable; one per recipient"
    )
    parser.add_argument("--smtp-host", default=os.environ.get(SMTP_HOST_ENV, ""))
    parser.add_argument(
        "--smtp-port",
        type=int,
        default=int(os.environ.get(SMTP_PORT_ENV, "587")),
    )
    parser.add_argument("--smtp-user", default=os.environ.get(SMTP_USERNAME_ENV, ""))
    parser.add_argument("--smtp-password", default=os.environ.get(SMTP_PASSWORD_ENV, ""))
    parser.add_argument("--no-starttls", dest="starttls", action="store_false", default=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rendered subject + body and exit; do not send.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = _build_arg_parser().parse_args(argv)
    try:
        summary = build_digest(ns.runs_root, project_name=ns.project_name)
    except DigestError as exc:
        sys.stderr.write(f"sentinelqa-digest: {exc}\n")
        return 2
    if ns.dry_run:
        digest = DigestEmail(
            subject=_subject_for(summary),
            text_body=render_text_digest(summary),
            html_body=render_html_digest(summary),
        )
        sys.stdout.write(digest.subject + "\n\n" + digest.text_body)
        return 0
    if not ns.smtp_host:
        sys.stderr.write(f"sentinelqa-digest: --smtp-host or {SMTP_HOST_ENV} is required.\n")
        return 2
    config = SmtpConfig(
        host=ns.smtp_host,
        port=ns.smtp_port,
        username=ns.smtp_user,
        password=ns.smtp_password,
        use_starttls=ns.starttls,
    )
    try:
        send_digest(
            summary,
            sender=ns.sender,
            recipients=tuple(ns.to),
            smtp=config,
        )
    except DigestError as exc:
        sys.stderr.write(f"sentinelqa-digest: {exc}\n")
        return 1
    sys.stdout.write("sent\n")
    return 0


__all__ = [
    "SMTP_HOST_ENV",
    "SMTP_PASSWORD_ENV",
    "SMTP_PORT_ENV",
    "SMTP_USERNAME_ENV",
    "DigestBuilder",
    "DigestEmail",
    "DigestError",
    "DigestSummary",
    "SmtpConfig",
    "Transport",
    "build_digest",
    "main",
    "render_html_digest",
    "render_text_digest",
    "send_digest",
]


# Silence the imports-only lint on `datetime` — kept for future use.
_ = datetime, Any
