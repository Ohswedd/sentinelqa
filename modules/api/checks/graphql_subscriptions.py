# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""GraphQL subscriptions check (v1.3.0).

The existing ``contract_graphql`` check covers queries + mutations.
Subscriptions are a different beast: they live over WebSockets,
ship messages indefinitely, and have their own abuse vectors
(N+1 fan-out, missing auth, no rate-limit).

Pure helpers — given a parsed schema fragment + a captured
subscription session, return structured findings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["critical", "high", "medium", "low", "info"]


@dataclass(frozen=True, slots=True)
class SubscriptionDefinition:
    """One field on the schema's ``Subscription`` type."""

    name: str
    return_type: str
    arguments: tuple[str, ...] = field(default_factory=tuple)
    has_directive_auth: bool = False


@dataclass(frozen=True, slots=True)
class SubscriptionSession:
    """A captured WebSocket-borne subscription session."""

    subscription_name: str
    accepted_unauthenticated: bool
    messages_per_second: float
    payload_caps_in_kib: int | None = None
    rate_limited: bool | None = None


@dataclass(frozen=True, slots=True)
class SubscriptionFinding:
    code: str
    severity: Severity
    subscription_name: str
    rationale: str
    suggested_fix: str = ""


# --------------------------------------------------------------------------- #
# Schema parsing — minimal, regex-based, sufficient for the auth check
# --------------------------------------------------------------------------- #

_SUB_BLOCK_RE = re.compile(
    r"type\s+Subscription\s*\{([^}]*)\}",
    re.IGNORECASE,
)
_FIELD_RE = re.compile(
    r"(\w+)\s*(?:\(([^)]*)\))?\s*:\s*([^\s@]+)(?:\s*@(\w+))?",
)


def parse_subscriptions(sdl: str) -> tuple[SubscriptionDefinition, ...]:
    """Extract every field on the ``Subscription`` type."""

    block_match = _SUB_BLOCK_RE.search(sdl)
    if block_match is None:
        return ()
    body = block_match.group(1)
    out: list[SubscriptionDefinition] = []
    for field_match in _FIELD_RE.finditer(body):
        name, args, return_type, directive = field_match.groups()
        args_tuple = tuple(a.strip().split(":")[0].strip() for a in args.split(",")) if args else ()
        out.append(
            SubscriptionDefinition(
                name=name,
                return_type=return_type.strip("[]!"),
                arguments=args_tuple,
                has_directive_auth=directive in {"auth", "requireAuth"},
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #


def evaluate_subscription_auth(
    definition: SubscriptionDefinition,
) -> tuple[SubscriptionFinding, ...]:
    """Flag subscriptions that don't declare an auth directive."""

    if definition.has_directive_auth:
        return ()
    return (
        SubscriptionFinding(
            code="GQL-SUB-NO-AUTH",
            severity="high",
            subscription_name=definition.name,
            rationale=(
                f"Subscription ``{definition.name}`` has no ``@auth`` / "
                "``@requireAuth`` directive. Anonymous clients can stream "
                "live data."
            ),
            suggested_fix=(
                "Add the project's auth directive to every Subscription "
                "field, and gate the resolver on ``context.user``."
            ),
        ),
    )


def evaluate_subscription_session(session: SubscriptionSession) -> tuple[SubscriptionFinding, ...]:
    """Flag abuse-prone behaviour observed in a live session."""

    out: list[SubscriptionFinding] = []
    if session.accepted_unauthenticated:
        out.append(
            SubscriptionFinding(
                code="GQL-SUB-ANON-ACCEPTED",
                severity="critical",
                subscription_name=session.subscription_name,
                rationale=(
                    "Server accepted an unauthenticated subscription. "
                    "Cross-Site GraphQL Subscription Hijacking is now "
                    "possible if the cookie is not SameSite=Strict."
                ),
                suggested_fix=(
                    "Reject anonymous handshakes; require a bearer token "
                    "or session cookie on every subscription connection."
                ),
            )
        )
    if session.messages_per_second > 100:
        out.append(
            SubscriptionFinding(
                code="GQL-SUB-HIGH-RATE",
                severity="medium",
                subscription_name=session.subscription_name,
                rationale=(
                    f"Stream emits {session.messages_per_second:.0f} msg/s, "
                    "exceeding the 100/s budget. Without rate-limiting one "
                    "noisy subscription can starve the others."
                ),
                suggested_fix="Add per-subscriber rate-limiting at the resolver.",
            )
        )
    if session.payload_caps_in_kib is None or session.payload_caps_in_kib > 256:
        out.append(
            SubscriptionFinding(
                code="GQL-SUB-NO-PAYLOAD-CAP",
                severity="medium",
                subscription_name=session.subscription_name,
                rationale=(
                    "Per-event payload cap is missing or > 256 KiB. An "
                    "attacker can subscribe and trigger oversized fan-out "
                    "events to exhaust memory."
                ),
                suggested_fix="Cap each event at 256 KiB before broadcast.",
            )
        )
    if session.rate_limited is False:
        out.append(
            SubscriptionFinding(
                code="GQL-SUB-NO-RATE-LIMIT",
                severity="medium",
                subscription_name=session.subscription_name,
                rationale="No per-IP / per-token connection limit enforced.",
                suggested_fix="Limit concurrent subscriptions per principal.",
            )
        )
    return tuple(out)


__all__ = [
    "SubscriptionDefinition",
    "SubscriptionFinding",
    "SubscriptionSession",
    "evaluate_subscription_auth",
    "evaluate_subscription_session",
    "parse_subscriptions",
]
