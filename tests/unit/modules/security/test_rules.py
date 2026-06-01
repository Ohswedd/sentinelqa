"""Tests for the security rule catalog."""

from __future__ import annotations

from engine.reporter.sarif_rules import SarifRuleRegistry

from modules.security.rules import (
    all_rules,
    register_security_rules,
    rule_by_category,
    rule_by_id,
)


def test_rule_ids_are_unique() -> None:
    ids = [r.rule_id for r in all_rules()]
    assert len(ids) == len(set(ids))


def test_all_ids_start_with_sec_prefix() -> None:
    assert all(r.rule_id.startswith("SEC-") for r in all_rules())


def test_lookup_helpers_round_trip() -> None:
    for rule in all_rules():
        assert rule_by_id(rule.rule_id) is rule
        assert rule_by_category(rule.category) is rule


def test_help_uri_is_stable() -> None:
    rule = rule_by_id("SEC-HEADERS-HSTS-MISSING")
    assert rule.help_uri.startswith("https://docs.sentinelqa.dev/rules/security/")
    assert "sec-headers-hsts-missing" in rule.help_uri


def test_register_security_rules_is_idempotent() -> None:
    reg = SarifRuleRegistry()
    register_security_rules(reg)
    first = len(list(reg.known_categories()))
    register_security_rules(reg)
    assert len(list(reg.known_categories())) == first


def test_register_security_rules_default_registry_idempotent() -> None:
    # Already registered as a side-effect of importing modules.security.
    # A second call must be a no-op.
    register_security_rules()
    register_security_rules()
