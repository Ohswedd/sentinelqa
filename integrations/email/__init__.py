# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Weekly email digest for SentinelQA runs (v1.6.0)."""

from __future__ import annotations

from integrations.email.digest import (
    SMTP_HOST_ENV,
    SMTP_PASSWORD_ENV,
    SMTP_PORT_ENV,
    SMTP_USERNAME_ENV,
    DigestBuilder,
    DigestEmail,
    DigestError,
    DigestSummary,
    SmtpConfig,
    build_digest,
    main,
    render_html_digest,
    render_text_digest,
    send_digest,
)

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
    "build_digest",
    "main",
    "render_html_digest",
    "render_text_digest",
    "send_digest",
]
