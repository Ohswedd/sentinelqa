"""LLM-CLIENT-SECRET-STORAGE — secrets in browser storage.

Pure function over :class:`BrowserStorageSample` records. Each entry's
value is passed through the redactor; if the redactor would
mask the value (it is a known secret category), or if the key name
matches a common token / credential pattern, we flag it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from engine.policy.redaction import redact

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import BrowserStorageSample
from modules.llm_audit.rules import LLM_CLIENT_SECRET_STORAGE

_SECRET_KEY_HINTS = re.compile(
    r"(?:token|jwt|bearer|session|access|auth|api[_-]?key|secret|credential)",
    re.IGNORECASE,
)
_JWT_VALUE = re.compile(r"^eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}$")


def check_localstorage_secrets(
    samples: Iterable[BrowserStorageSample],
) -> tuple[CheckFinding, ...]:
    findings: list[CheckFinding] = []
    for sample in samples:
        for key, value in sample.entries.items():
            if not value:
                continue
            redacted = redact(value)
            redactor_caught = isinstance(redacted, str) and "[REDACTED:" in redacted
            looks_like_jwt = bool(_JWT_VALUE.match(value.strip()))
            key_hint = bool(_SECRET_KEY_HINTS.search(key))
            if not (redactor_caught or looks_like_jwt or key_hint):
                continue
            reason = (
                "matches a redaction rule"
                if redactor_caught
                else ("looks like a JWT" if looks_like_jwt else "has a secret-like key name")
            )
            findings.append(
                CheckFinding(
                    rule_id=LLM_CLIENT_SECRET_STORAGE.id,
                    title=f"{sample.store} on {sample.route_url} stores {key!r}",
                    description=(
                        f"{sample.store} key {key!r} on {sample.route_url} "
                        f"{reason}. XSS payloads read browser storage trivially; "
                        "HttpOnly+Secure cookies are out of script reach."
                    ),
                    route=sample.route_url,
                    extra_context=(
                        ("store", sample.store),
                        ("key", key),
                        ("reason", reason),
                    ),
                )
            )
    return tuple(findings)


__all__ = ["check_localstorage_secrets"]
