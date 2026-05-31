"""Phase 34.05 — compliance-pack DSL loader + validator."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.policy.compliance import (
    CompliancePack,
    CompliancePackError,
    builtin_pack_dir,
    known_checks,
    known_modules,
    load_compliance_pack,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Known-module registry
# ---------------------------------------------------------------------------


def test_known_modules_includes_compliance_and_accessibility() -> None:
    modules = set(known_modules())
    assert {"accessibility", "compliance", "security", "supply_chain"}.issubset(modules)


def test_known_checks_for_compliance() -> None:
    assert known_checks("compliance") == frozenset({"gdpr", "ccpa", "soc2_trail", "wcag22"})


def test_known_checks_for_unknown_module_returns_empty() -> None:
    assert known_checks("nonexistent") == frozenset()


# ---------------------------------------------------------------------------
# Built-in pack loading
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pack_id",
    ["wcag-2.2-aa", "gdpr-baseline", "ccpa-baseline", "soc2-trail"],
)
def test_builtin_pack_loads_cleanly(pack_id: str) -> None:
    pack = load_compliance_pack(pack_id)
    assert isinstance(pack, CompliancePack)
    assert pack.id == pack_id
    assert pack.label.endswith("(automated)")
    assert pack.includes


def test_builtin_pack_dir_resolves_to_repo() -> None:
    expected = REPO_ROOT / "policy" / "compliance"
    assert builtin_pack_dir() == expected
    assert (expected / "wcag-2.2-aa.yaml").exists()


def test_wcag_22_aa_pack_requests_both_modules() -> None:
    pack = load_compliance_pack("wcag-2.2-aa")
    assert pack.requested_modules() == ("accessibility", "compliance")
    options = pack.module_options()
    assert "axe_tags" in options["accessibility"]
    assert options["compliance"]["enabled_checks"] == ("wcag22",)


def test_gdpr_baseline_pack_sets_flag_missing_consent_banner() -> None:
    pack = load_compliance_pack("gdpr-baseline")
    opts = pack.module_options()["compliance"]
    assert opts["flag_missing_consent_banner"] is True
    assert opts["enabled_checks"] == ("gdpr",)


def test_ccpa_baseline_pack_sets_enforce_link_presence() -> None:
    pack = load_compliance_pack("ccpa-baseline")
    opts = pack.module_options()["compliance"]
    assert opts["enforce_ccpa_link_presence"] is True
    assert opts["enabled_checks"] == ("ccpa",)


def test_soc2_trail_pack_only_lists_soc2_check() -> None:
    pack = load_compliance_pack("soc2-trail")
    opts = pack.module_options()["compliance"]
    assert opts["enabled_checks"] == ("soc2_trail",)


def test_pack_fail_on_warn_on_propagate() -> None:
    pack = load_compliance_pack("wcag-2.2-aa")
    assert pack.fail_severities() == ("critical", "high")
    assert pack.warn_severities() == ("medium",)


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_missing_pack_id_raises(tmp_path: Path) -> None:
    pack_path = tmp_path / "bad.yaml"
    pack_path.write_text("pack:\n  label: oops\n", encoding="utf-8")
    with pytest.raises(CompliancePackError) as info:
        load_compliance_pack(pack_path)
    assert "id" in str(info.value)


def test_unknown_module_raises(tmp_path: Path) -> None:
    pack_path = tmp_path / "bad.yaml"
    pack_path.write_text(
        "pack:\n"
        "  id: bad-pack\n"
        "  label: Bad\n"
        "  version: 1\n"
        "  includes:\n"
        "    - module: nonexistent\n",
        encoding="utf-8",
    )
    with pytest.raises(CompliancePackError) as info:
        load_compliance_pack(pack_path)
    assert "not a known SentinelQA module" in str(info.value)


def test_unknown_check_raises(tmp_path: Path) -> None:
    pack_path = tmp_path / "bad.yaml"
    pack_path.write_text(
        "pack:\n"
        "  id: bad-checks\n"
        "  label: Bad\n"
        "  version: 1\n"
        "  includes:\n"
        "    - module: compliance\n"
        "      checks: [doesnt_exist]\n",
        encoding="utf-8",
    )
    with pytest.raises(CompliancePackError) as info:
        load_compliance_pack(pack_path)
    assert "doesnt_exist" in str(info.value)


def test_check_filter_on_module_without_checks_raises(tmp_path: Path) -> None:
    pack_path = tmp_path / "bad.yaml"
    pack_path.write_text(
        "pack:\n"
        "  id: bad-filter\n"
        "  label: Bad\n"
        "  version: 1\n"
        "  includes:\n"
        "    - module: security\n"
        "      checks: [headers]\n",
        encoding="utf-8",
    )
    with pytest.raises(CompliancePackError) as info:
        load_compliance_pack(pack_path)
    assert "does not support" in str(info.value)


def test_pack_with_unknown_top_level_key_rejected(tmp_path: Path) -> None:
    pack_path = tmp_path / "bad.yaml"
    pack_path.write_text(
        "pack:\n" "  id: bad-extra\n" "  label: Bad\n" "  version: 1\n" "  bogus_field: true\n",
        encoding="utf-8",
    )
    with pytest.raises(CompliancePackError):
        load_compliance_pack(pack_path)


def test_pack_missing_top_level_pack_key_raises(tmp_path: Path) -> None:
    pack_path = tmp_path / "bad.yaml"
    pack_path.write_text("not_a_pack: 1\n", encoding="utf-8")
    with pytest.raises(CompliancePackError) as info:
        load_compliance_pack(pack_path)
    assert "top-level 'pack:'" in str(info.value)


def test_missing_pack_id_raises_not_found() -> None:
    with pytest.raises(CompliancePackError) as info:
        load_compliance_pack("not-a-real-pack")
    assert "not found" in str(info.value)


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("pack: [oops\n", encoding="utf-8")
    with pytest.raises(CompliancePackError) as info:
        load_compliance_pack(bad)
    assert "valid YAML" in str(info.value)


# ---------------------------------------------------------------------------
# Pack composition
# ---------------------------------------------------------------------------


def test_pack_with_repeated_module_merges_options_and_checks(tmp_path: Path) -> None:
    pack_path = tmp_path / "merged.yaml"
    pack_path.write_text(
        "pack:\n"
        "  id: merged-pack\n"
        "  label: Merged (automated)\n"
        "  version: 1\n"
        "  includes:\n"
        "    - module: compliance\n"
        "      options:\n"
        "        flag_missing_consent_banner: true\n"
        "      checks: [gdpr]\n"
        "    - module: compliance\n"
        "      options:\n"
        "        enforce_ccpa_link_presence: false\n"
        "      checks: [ccpa]\n",
        encoding="utf-8",
    )
    pack = load_compliance_pack(pack_path)
    opts = pack.module_options()["compliance"]
    assert opts["flag_missing_consent_banner"] is True
    assert opts["enforce_ccpa_link_presence"] is False
    assert opts["enabled_checks"] == ("gdpr", "ccpa")
