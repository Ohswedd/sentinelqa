"""Tests for the prefix-based ID generator and validator."""

from __future__ import annotations

import re

import pytest
from engine.domain.ids import (
    ENTITY_PREFIXES,
    ID_REGEX,
    IdGenerator,
    validate_id,
)


def test_id_regex_round_trip() -> None:
    gen = IdGenerator()
    for prefix in ENTITY_PREFIXES:
        new = gen.new(prefix)
        assert ID_REGEX.match(new), f"Generator produced an invalid ID: {new}"
        assert new.startswith(f"{prefix}-")


def test_validate_id_accepts_correct_prefix() -> None:
    gen = IdGenerator()
    new = gen.new("RUN")
    assert validate_id(new, prefix="RUN") == new


def test_validate_id_rejects_wrong_prefix() -> None:
    gen = IdGenerator()
    new = gen.new("RUN")
    with pytest.raises(ValueError, match="does not start with required prefix"):
        validate_id(new, prefix="FND")


def test_validate_id_rejects_malformed() -> None:
    with pytest.raises(ValueError, match="not a valid SentinelQA ID"):
        validate_id("not-an-id")


def test_unknown_prefix_rejected() -> None:
    gen = IdGenerator()
    with pytest.raises(ValueError, match="Unknown entity prefix"):
        gen.new("ZZZ")


def test_ids_unique_in_bulk() -> None:
    """1 000 generations from the same instance should collide zero times."""

    gen = IdGenerator()
    ids = {gen.new("FND") for _ in range(1000)}
    assert len(ids) == 1000


def test_id_regex_is_anchored() -> None:
    """ID regex must reject extra characters at either end."""

    assert ID_REGEX.match("RUN-AAAAAAAAAAAA") is not None
    assert ID_REGEX.match("xRUN-AAAAAAAAAAAA") is None
    assert ID_REGEX.match("RUN-AAAAAAAAAAAAx") is None
    # Lowercase prefix is rejected.
    assert ID_REGEX.match("run-AAAAAAAAAAAA") is None


def test_alphabet_avoids_ambiguous_letters() -> None:
    """Slugs never contain I, L, O, U (Crockford base32 reasoning)."""

    gen = IdGenerator()
    slugs = "".join(gen.new("RUN").split("-")[1] for _ in range(50))
    assert not re.search(r"[ILOU]", slugs)
