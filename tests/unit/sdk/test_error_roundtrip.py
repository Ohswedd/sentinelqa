"""Public error round-trip via ``sentinelqa.errors.from_dict``."""

from __future__ import annotations

import pytest

from sentinelqa import (
    ConfigError,
    DependencyMissingError,
    QualityGateFailedError,
    SentinelError,
    TestExecutionError,
    UnsafeTargetError,
)
from sentinelqa.errors import (
    ConfigFileNotFoundError,
    ConfigSchemaError,
    ConfigSecretInlineError,
    DestructiveWithoutProofError,
    ForbiddenFlagError,
    UnknownHostError,
    from_dict,
)


def test_roundtrip_preserves_code_and_exit_code() -> None:
    err = UnknownHostError(host="evil.example.com")
    msg = err.to_agent_message()
    rebuilt = from_dict(msg)
    assert isinstance(rebuilt, UnknownHostError)
    assert isinstance(rebuilt, UnsafeTargetError)
    assert rebuilt.code == err.code
    assert rebuilt.exit_code == err.exit_code
    assert rebuilt.suggested_fix == err.suggested_fix


@pytest.mark.parametrize(
    ("error_cls", "kwargs"),
    [
        (ConfigFileNotFoundError, {"path": "missing.yaml"}),
        (ConfigSchemaError, {"detail": "missing target.base_url"}),
        (ConfigSecretInlineError, {"field": "auth.password"}),
        (UnknownHostError, {"host": "example.com"}),
        (DestructiveWithoutProofError, {"host": "example.com"}),
        (ForbiddenFlagError, {"flag": "--forbidden-example"}),
        (DependencyMissingError, {"dependency": "playwright"}),
        (TestExecutionError, {"detail": "Playwright timed out"}),
        (QualityGateFailedError, {"detail": "score 73 < 85"}),
    ],
)
def test_roundtrip_picks_specific_subclass(
    error_cls: type[SentinelError], kwargs: dict[str, str]
) -> None:
    err = error_cls(**kwargs)
    rebuilt = from_dict(err.to_agent_message())
    assert isinstance(rebuilt, error_cls)
    assert rebuilt.code == err.code
    # Reconstructed instance carries the same exit code as the original.
    assert rebuilt.exit_code == err.exit_code


def test_unknown_code_degrades_to_generic_sentinel_error() -> None:
    msg = {
        "type": "error",
        "code": "E-FUTURE-999",
        "exit_code": 3,
        "message": "Some future code",
        "suggested_fix": "Upgrade SentinelQA.",
        "context": {},
    }
    rebuilt = from_dict(msg)
    assert isinstance(rebuilt, SentinelError)
    assert rebuilt.code == "E-FUTURE-999"
    assert rebuilt.exit_code == 3


def test_from_dict_rejects_missing_code() -> None:
    with pytest.raises(ValueError, match="'code'"):
        from_dict({"type": "error"})


def test_from_dict_rejects_non_mapping_input() -> None:
    with pytest.raises(TypeError):
        from_dict("not a mapping")  # type: ignore[arg-type]


def test_from_dict_rejects_non_string_message() -> None:
    with pytest.raises(ValueError, match="message"):
        from_dict(
            {
                "type": "error",
                "code": "E-CFG-002",
                "message": 123,
            }
        )


def test_from_dict_rejects_non_string_suggested_fix() -> None:
    with pytest.raises(ValueError, match="suggested_fix"):
        from_dict(
            {
                "type": "error",
                "code": "E-CFG-002",
                "suggested_fix": ["nope"],
            }
        )


def test_from_dict_rejects_non_int_exit_code() -> None:
    with pytest.raises(ValueError, match="exit_code"):
        from_dict(
            {
                "type": "error",
                "code": "E-CFG-002",
                "exit_code": "two",
            }
        )


def test_from_dict_rejects_non_mapping_context() -> None:
    with pytest.raises(ValueError, match="context"):
        from_dict(
            {
                "type": "error",
                "code": "E-CFG-002",
                "context": ["x"],
            }
        )


def test_from_dict_preserves_redacted_message() -> None:
    # `to_agent_message` redacts the message; reconstruction must keep
    # the redacted form (we never un-redact).
    err = TestExecutionError(detail="failure")
    redacted_msg = err.to_agent_message()
    rebuilt = from_dict(redacted_msg)
    assert rebuilt.message == redacted_msg["message"]


def test_config_subclass_inherits_from_config_error() -> None:
    err = ConfigSchemaError(detail="bad schema")
    rebuilt = from_dict(err.to_agent_message())
    assert isinstance(rebuilt, ConfigError)
    assert isinstance(rebuilt, ConfigSchemaError)
