"""SARIF rule registry (task 03.05).

Module phases (13+) register their rules here. The SARIF writer asks the
registry for the rule that matches a finding's category and falls back
to a synthesized rule when none is registered, so output is always
schema-valid (CLAUDE.md §37 — no fake completion: a missing rule is
visible in the output as an explicit synthesized entry).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class SarifRule:
    """One SARIF rule descriptor.

    Mirrors the SARIF 2.1.0 ``reportingDescriptor`` shape with only the
    fields Phase 03 ships. Phase 24's plugin contract may add more.
    """

    id: str
    name: str
    short_description: str
    full_description: str
    help_uri: str
    category: str
    default_severity: str = "warning"

    def to_descriptor(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "shortDescription": {"text": self.short_description},
            "fullDescription": {"text": self.full_description},
            "helpUri": self.help_uri,
            "properties": {"category": self.category},
            "defaultConfiguration": {"level": self.default_severity},
        }


_HELP_BASE: Final[str] = "https://docs.sentinelqa.dev/rules/"


class SarifRuleRegistry:
    """In-memory registry of :class:`SarifRule` descriptors.

    Lookups are by *category* (e.g. ``security/headers``). Module phases
    register the rules they emit; the writer falls back to a synthesized
    placeholder when a category is unknown (so output is always valid).
    """

    def __init__(self) -> None:
        self._by_category: dict[str, SarifRule] = {}

    def register(self, rule: SarifRule) -> None:
        if rule.category in self._by_category:
            raise ValueError(f"SARIF rule for category {rule.category!r} is already registered.")
        self._by_category[rule.category] = rule

    def get(self, category: str) -> SarifRule:
        existing = self._by_category.get(category)
        if existing is not None:
            return existing
        return self.synthesize(category)

    def known_categories(self) -> Iterable[str]:
        return tuple(sorted(self._by_category))

    def clear(self) -> None:  # test helper
        self._by_category.clear()

    @staticmethod
    def synthesize(category: str) -> SarifRule:
        """Return a placeholder rule when ``category`` is not registered.

        The id is deterministic from the category so callers can still
        cross-reference findings by ruleId. Module phases (Phase 13+) will
        register real rules and the synthesized fallback will become rare.
        """

        canonical = category.replace("/", "-").replace("_", "-").upper()
        rid = f"GEN-{canonical}"
        return SarifRule(
            id=rid,
            name=canonical or "UnknownRule",
            short_description=f"Unregistered SentinelQA rule {category!r}.",
            full_description=(
                f"No SARIF rule has been registered for category {category!r} yet. "
                "This is a placeholder synthesized by Phase 03's SARIF writer; "
                "later phases will register a real rule before they emit findings."
            ),
            help_uri=_HELP_BASE + rid,
            category=category,
        )


# Process-wide registry; module phases append to it. Tests build a fresh
# registry via ``SarifRuleRegistry()`` rather than mutating this one.
_DEFAULT_REGISTRY = SarifRuleRegistry()


def default_sarif_registry() -> SarifRuleRegistry:
    return _DEFAULT_REGISTRY


__all__ = [
    "SarifRule",
    "SarifRuleRegistry",
    "default_sarif_registry",
]
