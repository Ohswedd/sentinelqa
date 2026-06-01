"""— protocol versioning contract."""

from __future__ import annotations

import pytest
from engine.plugins import PROTOCOL_VERSION, is_compatible, parse_requires_protocol
from engine.plugins.errors import PluginManifestError


def test_protocol_version_matches_sdk() -> None:
    import sentinelqa.plugins as sdk

    assert PROTOCOL_VERSION == sdk.PROTOCOL_VERSION


def test_parse_requires_protocol_accepts_canonical_range() -> None:
    spec = parse_requires_protocol(">=1.0,<2.0")
    assert spec.contains("1.0.0")
    assert not spec.contains("2.0.0")


def test_parse_requires_protocol_accepts_exact_pin() -> None:
    spec = parse_requires_protocol("==1.0.0")
    assert spec.contains("1.0.0")
    assert not spec.contains("1.0.1")


def test_parse_requires_protocol_rejects_garbage() -> None:
    with pytest.raises(PluginManifestError):
        parse_requires_protocol("not-a-spec")


def test_is_compatible_with_current_version() -> None:
    assert is_compatible(">=1.0,<2.0")
    assert is_compatible("==1.0.0")
    assert is_compatible(">=1.0")


def test_is_incompatible_with_future_version() -> None:
    assert not is_compatible(">=2.0")
    assert not is_compatible("<1.0")


def test_empty_requires_protocol_means_any() -> None:
    assert is_compatible("")
    assert is_compatible("   ")


def test_is_compatible_uses_host_override() -> None:
    # Pin host to 2.0 to check the override works (used by tests +
    # the future major-bump path).
    assert is_compatible(">=2.0", host="2.0.0")
    assert not is_compatible(">=2.0", host="1.0.0")
