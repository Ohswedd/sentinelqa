"""Secret-in-bundle scanner.

For every JS bundle Playwright loaded during the run, fetch the bundle
(streamed, capped at ``max_bytes`` — default 50 MiB) and scan for the
canonical credential-shape patterns. Bundles larger than the cap are
truncated and a ``truncated: true`` flag rides on the finding so the
operator knows a tail was not inspected.

The pattern set deliberately re-uses the rule ids the Phase-29 audit
codified (CWE-540) plus the Anthropic-Skills-derived additions called
out in the README. No bundle bytes are persisted in the audit
log; only the bundle URL + redacted prefix of each match.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

import httpx
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.models import SecurityCheckResult, SecurityIssue

CHECK_NAME = "bundle_secrets"

_DEFAULT_MAX_BYTES: Final[int] = 50 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SecretPattern:
    """One regex with metadata for a credential-shape detector."""

    rule_id: str
    name: str
    regex: re.Pattern[str]
    cwe_id: str = "CWE-540"


# Pattern order is fixed; the safety guard at
# ``tests/security/test_no_offensive_checks.py`` greps the module to
# prove no `for... in <external resource>` loop exists.
_PATTERNS: Final[tuple[SecretPattern, ...]] = (
    SecretPattern(
        rule_id="SEC-BUNDLE-SECRET-AWS",
        name="aws_access_key",
        regex=re.compile(r"AKIA[0-9A-Z]{16}"),
    ),
    SecretPattern(
        rule_id="SEC-BUNDLE-SECRET-GCP",
        name="gcp_api_key",
        regex=re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    ),
    SecretPattern(
        rule_id="SEC-BUNDLE-SECRET-AZURE",
        name="azure_subscription_key",
        regex=re.compile(
            r"(?:subscription[_-]?key|ocp-apim-subscription-key)[^a-zA-Z0-9]+([a-f0-9]{32})",
            re.IGNORECASE,
        ),
    ),
    SecretPattern(
        rule_id="SEC-BUNDLE-SECRET-STRIPE",
        name="stripe_live",
        regex=re.compile(r"sk_live_[0-9A-Za-z]{24,}"),
    ),
    SecretPattern(
        rule_id="SEC-BUNDLE-SECRET-GITHUB",
        name="github_token",
        regex=re.compile(r"gh[pousr]_[0-9A-Za-z]{36,}"),
    ),
    SecretPattern(
        rule_id="SEC-BUNDLE-SECRET-SLACK",
        name="slack_token",
        regex=re.compile(r"xox[abprs]-[0-9A-Za-z-]{10,}"),
    ),
    SecretPattern(
        rule_id="SEC-BUNDLE-SECRET-PRIVATE-KEY",
        name="pem_private_key",
        regex=re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
)


@dataclass(frozen=True, slots=True)
class BundleScanResult:
    url: str
    truncated: bool
    matches: tuple[tuple[str, str], ...]
    """Tuple of ``(rule_id, redacted_prefix)`` pairs."""


def _redact_match(match: str) -> str:
    if len(match) <= 8:
        return f"{match[:4]}…"
    return f"{match[:8]}…"


def scan_bundle_text(url: str, text: str, *, truncated: bool = False) -> BundleScanResult:
    """Pure scanner — no I/O. Returns redacted matches per rule."""

    matches: list[tuple[str, str]] = []
    for pattern in _PATTERNS:
        for hit in pattern.regex.finditer(text):
            matched = hit.group(0)
            matches.append((pattern.rule_id, _redact_match(matched)))
    return BundleScanResult(url=url, truncated=truncated, matches=tuple(matches))


def evaluate_bundle_scan(result: BundleScanResult) -> Iterable[SecurityIssue]:
    for rule_id, prefix in result.matches:
        pattern = next(p for p in _PATTERNS if p.rule_id == rule_id)
        evidence = {
            "bundle_url": result.url,
            "match_prefix": prefix,
            "cwe_id": pattern.cwe_id,
        }
        if result.truncated:
            evidence["truncated"] = "true"
        yield SecurityIssue(
            rule_id=rule_id,
            severity="critical" if "STRIPE" in rule_id or "PRIVATE-KEY" in rule_id else "high",
            confidence=0.9,
            title=f"Possible {pattern.name} in JS bundle {result.url}",
            description=(
                "A SentinelQA detector pattern matched inside a JavaScript "
                f"bundle served to the browser. {pattern.name} credentials "
                "in client code are recoverable by anyone. CWE-540."
            ),
            route=result.url,
            evidence=evidence,
            recommendation=("Move the credential server-side; rotate the exposed key."),
        )


def fetch_bundle(
    client: httpx.Client,
    url: str,
    *,
    max_bytes: int = _DEFAULT_MAX_BYTES,
) -> tuple[str, bool]:
    """Stream the bundle into memory, capped at ``max_bytes``.

    Returns ``(text, truncated)``.
    """

    chunks: list[bytes] = []
    received = 0
    truncated = False
    with client.stream("GET", url, timeout=30.0) as response:
        response.raise_for_status()
        ctype = response.headers.get("content-type", "")
        if "javascript" not in ctype and not url.endswith(".js"):
            return "", False
        for chunk in response.iter_bytes():
            if received + len(chunk) > max_bytes:
                remaining = max_bytes - received
                chunks.append(chunk[:remaining])
                received = max_bytes
                truncated = True
                break
            chunks.append(chunk)
            received += len(chunk)
    text = b"".join(chunks).decode("utf-8", errors="replace")
    return text, truncated


def run_bundle_secrets_check(
    ctx: CheckContext,
    *,
    bundle_urls: Sequence[str],
    max_bytes: int = _DEFAULT_MAX_BYTES,
) -> SecurityCheckResult:
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    start = time.monotonic()
    issues: list[SecurityIssue] = []
    scanned = 0
    for url in bundle_urls:
        try:
            text, truncated = fetch_bundle(ctx.client, url, max_bytes=max_bytes)
        except httpx.HTTPError as exc:
            _audit(ctx, kind="error", detail=f"{url}: {exc}")
            continue
        if not text:
            continue
        scanned += 1
        result = scan_bundle_text(url, text, truncated=truncated)
        issues.extend(evaluate_bundle_scan(result))
        _audit(
            ctx,
            kind="probe",
            detail=f"{url} truncated={truncated} matches={len(result.matches)}",
        )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=scanned,
        issues=tuple(issues),
        duration_ms=elapsed_ms,
    )


def _audit(ctx: CheckContext, *, kind: str, detail: str) -> None:
    if ctx.audit_log_path is None:
        return
    write_audit_entry(
        ctx.audit_log_path,
        {
            "event": f"security.{CHECK_NAME}.{kind}",
            "run_id": ctx.run_id,
            "detail": detail,
        },
    )


PATTERNS = _PATTERNS


__all__ = [
    "CHECK_NAME",
    "BundleScanResult",
    "PATTERNS",
    "SecretPattern",
    "evaluate_bundle_scan",
    "fetch_bundle",
    "run_bundle_secrets_check",
    "scan_bundle_text",
]
