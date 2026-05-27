"""SentinelQA policy layer.

Owns the safety boundary, target allowlist, audit logging, redaction, and
the proof-of-authorization gate (PRD §2, §23; CLAUDE.md §6, §33).
"""

from __future__ import annotations

from engine.policy.audit_log import read_audit_log, write_audit_entry
from engine.policy.forbidden_features import (
    FORBIDDEN_CAPABILITIES,
    FORBIDDEN_CLI_FLAGS,
    assert_capability_allowed,
    assert_flag_allowed,
)
from engine.policy.proof_of_authorization import (
    ProofOfAuthorization,
    load_proof,
    require_proof,
)
from engine.policy.redaction import (
    BUILTIN_RULES,
    SECRET_KEY_NAMES,
    RedactionRule,
    add_allowlist_token,
    clear_allowlist,
    redact,
    redact_headers,
    redact_in_place,
    redact_url,
)
from engine.policy.safety import SafetyDecision, SafetyPolicy, is_local

__all__ = [
    "redact",
    "redact_headers",
    "redact_url",
    "redact_in_place",
    "RedactionRule",
    "BUILTIN_RULES",
    "SECRET_KEY_NAMES",
    "add_allowlist_token",
    "clear_allowlist",
    "SafetyPolicy",
    "SafetyDecision",
    "is_local",
    "FORBIDDEN_CAPABILITIES",
    "FORBIDDEN_CLI_FLAGS",
    "assert_capability_allowed",
    "assert_flag_allowed",
    "ProofOfAuthorization",
    "load_proof",
    "require_proof",
    "write_audit_entry",
    "read_audit_log",
]
