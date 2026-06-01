"""Common Pydantic base for every domain model (our engineering rules, §20)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class SentinelModel(BaseModel):
    """Base for every entity in `engine.domain`.

    Properties enforced:

    - ``frozen=True`` — instances are hashable and immutable. Mutations
      flow through ``model_copy(update=...)``, which keeps audit trails clean.
    - ``extra="forbid"`` — unknown fields raise a ``ValidationError``. This
      protects schema stability (our engineering rules, §38) and stops silent drift.
    - ``str_strip_whitespace=True`` and ``str_min_length=0`` keep textual
      fields predictable when they ride through YAML/JSON.
    - ``populate_by_name=True`` allows alias-driven I/O while still keeping
      Python attribute names canonical.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
        validate_assignment=True,
    )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict using model field names.

        Wraps :py:meth:`pydantic.BaseModel.model_dump` with ``mode="json"`` so
        callers don't need to remember the right invocation; the resulting
        dict is safe to hand to ``json.dumps`` directly.
        """

        return self.model_dump(mode="json")


__all__ = ["SentinelModel"]
