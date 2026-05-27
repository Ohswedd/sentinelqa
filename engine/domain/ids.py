"""Prefix-based ID generator for every SentinelQA entity.

IDs are short, human-scannable, and collision-resistant. The format is::

    <PREFIX>-<SLUG>

where ``PREFIX`` identifies the entity type (e.g. ``RUN``, ``FND``, ``MOD``)
and ``SLUG`` is 12 base32 (Crockford-style) characters drawn from
``secrets.token_bytes``. That gives ~60 bits of entropy per ID — well above
the ``2**32`` threshold where a birthday collision becomes plausible inside
a single run, and short enough that humans can copy/paste IDs into chat or
issue trackers without truncation.

The full regex is anchored::

    ^[A-Z]{2,4}-[A-Z0-9]{12}$

IDs are validated by :func:`validate_id` at the model boundary, so domain
models can use ``Field(pattern=...)`` to reject malformed inputs.
"""

from __future__ import annotations

import re
import secrets
from typing import Final

# Crockford base32 alphabet, minus the ambiguous letters I, L, O, U.
_ALPHABET: Final[str] = "ABCDEFGHJKMNPQRSTVWXYZ23456789"
_SLUG_LEN: Final[int] = 12
_PREFIX_LEN_MIN: Final[int] = 2
_PREFIX_LEN_MAX: Final[int] = 4

# Canonical regex used by validators throughout the codebase. Kept here so
# every consumer references the same string and so the regex itself is
# unit-tested.
ID_REGEX: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{2,4}-[A-Z0-9]{12}$")

# Reserved entity prefixes. Adding a new entity requires adding its prefix
# here so collisions across entity types are impossible by construction.
ENTITY_PREFIXES: Final[frozenset[str]] = frozenset(
    {
        "PRJ",  # Project
        "TGT",  # Target
        "RUN",  # TestRun
        "MOD",  # ModuleResult
        "FND",  # Finding
        "EVD",  # Evidence
        "FLW",  # Flow
        "TC",  # TestCase
        "RT",  # Route
        "EL",  # Element
        "FRM",  # Form
        "API",  # ApiEndpoint
        "SCR",  # QualityScore
        "PD",  # PolicyDecision
        "RPR",  # RepairSuggestion
        "DG",  # DiscoveryGraph
        "RM",  # RiskMap
    }
)


class IdGenerator:
    """Stateless ID generator.

    Implemented as a class (rather than a free function) so test suites can
    monkeypatch :py:meth:`_random_slug` to make IDs deterministic without
    monkeypatching ``secrets`` itself. Production code uses the default
    :func:`secrets.token_bytes`-backed implementation.
    """

    def new(self, prefix: str) -> str:
        """Return a new ID with the given ``prefix``.

        Raises ``ValueError`` if ``prefix`` is not a registered entity prefix.
        """

        if prefix not in ENTITY_PREFIXES:
            raise ValueError(
                f"Unknown entity prefix {prefix!r}; "
                f"register it in engine.domain.ids.ENTITY_PREFIXES first."
            )
        return f"{prefix}-{self._random_slug()}"

    def _random_slug(self) -> str:
        # 12 random characters drawn uniformly from the 30-symbol alphabet,
        # using rejection sampling on bytes from `secrets.token_bytes` so the
        # output distribution is genuinely uniform (not biased like a naive
        # modulo would be).
        out: list[str] = []
        alphabet_size = len(_ALPHABET)
        # The largest byte value that maps cleanly without modulo bias.
        cutoff = 256 - (256 % alphabet_size)
        while len(out) < _SLUG_LEN:
            for byte in secrets.token_bytes(_SLUG_LEN * 2):
                if byte >= cutoff:
                    continue
                out.append(_ALPHABET[byte % alphabet_size])
                if len(out) == _SLUG_LEN:
                    break
        return "".join(out)


def validate_id(value: str, *, prefix: str | None = None) -> str:
    """Validate ``value`` against :data:`ID_REGEX`.

    If ``prefix`` is given, also enforces that the ID begins with that exact
    prefix. Returns the input unchanged on success, raises ``ValueError`` on
    failure — suitable for use as a Pydantic ``field_validator``.
    """

    if not ID_REGEX.match(value):
        raise ValueError(
            f"{value!r} is not a valid SentinelQA ID " f"(expected pattern {ID_REGEX.pattern})."
        )
    if prefix is not None and not value.startswith(f"{prefix}-"):
        raise ValueError(f"{value!r} does not start with required prefix {prefix!r}.")
    return value


__all__ = [
    "ID_REGEX",
    "ENTITY_PREFIXES",
    "IdGenerator",
    "validate_id",
]
