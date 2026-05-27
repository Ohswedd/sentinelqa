"""Form entity (PRD §18.1)."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import AnyUrl, Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.ids import validate_id
from engine.domain.route import HttpMethod
from engine.domain.schema import CONFIG_SCHEMA_VERSION

FormFieldType = Literal[
    "text",
    "email",
    "password",
    "tel",
    "url",
    "number",
    "checkbox",
    "radio",
    "select",
    "textarea",
    "file",
    "date",
    "hidden",
    "unknown",
]


class FormField(SentinelModel):
    """One field inside a :class:`Form`."""

    name: str = Field(min_length=1, max_length=200)
    type: FormFieldType = "unknown"
    required: bool = False
    accessible_label: str | None = Field(default=None, max_length=512)
    placeholder: str | None = Field(default=None, max_length=512)


class Form(SentinelModel):
    """A discovered HTML form."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    id: str
    action_url: AnyUrl | None = None
    method: HttpMethod = "POST"
    fields: tuple[FormField, ...] = Field(default_factory=tuple)
    submit_handler_present: bool = False
    validation_present: bool = False

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return validate_id(value, prefix="FRM")


__all__ = ["Form", "FormField", "FormFieldType"]
