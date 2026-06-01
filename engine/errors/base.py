"""Typed exception hierarchy.

Each concrete exception declares its symbolic ``DEFAULT_CODE`` from the
registry; the base class :class:`SentinelError` does the work of looking up
the message template, exit code, and suggested fix at construction time, so
call sites stay terse::

    raise ConfigSchemaError(detail="missing required key 'target.base_url'")

The CLI catches :class:`SentinelError` at its outermost boundary and maps it
to an exit code via ``error.exit_code``. Anything that escapes as a plain
``Exception`` is funneled into :class:`InternalError` (exit code 7).
"""

from __future__ import annotations

from typing import Any, ClassVar

from engine.errors.codes import (
    ERROR_REGISTRY,
    EXIT_INTERNAL_ERROR,
    EXIT_RUNTIME_ERROR,
    ErrorCodeSpec,
)


class SentinelError(Exception):
    """Base for every SentinelQA exception that crosses a public boundary.

    Concrete subclasses set :attr:`DEFAULT_CODE` to a key registered in
    :data:`engine.errors.codes.ERROR_REGISTRY`. Construction reads the spec
    and applies it, but every field can still be overridden per-call.
    """

    DEFAULT_CODE: ClassVar[str] = "E-INT-001"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        exit_code: int | None = None,
        technical_context: dict[str, Any] | None = None,
        suggested_fix: str | None = None,
        **template_fields: Any,
    ) -> None:
        resolved_code = code or self.DEFAULT_CODE
        spec: ErrorCodeSpec | None = ERROR_REGISTRY.get(resolved_code)

        if message is None and spec is not None:
            try:
                message = spec.message_template.format(**template_fields)
            except KeyError:
                # Missing template fields is a programming bug, not a user
                # error — surface it with a stable, readable fallback.
                message = spec.message_template

        if message is None:
            message = "Unspecified SentinelQA error."

        self.code: str = resolved_code
        self.message: str = message
        self.exit_code: int = (
            exit_code
            if exit_code is not None
            else (spec.exit_code if spec is not None else EXIT_RUNTIME_ERROR)
        )
        self.technical_context: dict[str, Any] = dict(technical_context or {})
        if template_fields:
            # Preserve template inputs so the agent message carries enough
            # context for the SDK consumer (Phase 16) to render them too.
            for key, value in template_fields.items():
                self.technical_context.setdefault(key, value)
        self.suggested_fix: str = (
            suggested_fix
            if suggested_fix is not None
            else (spec.suggested_fix if spec is not None else "")
        )

        super().__init__(self.message)

    def to_agent_message(self) -> dict[str, Any]:
        """Serialize for SDK/MCP consumers (redaction applied)."""

        # Local import avoids a circular dependency: redaction lives in
        # engine.policy and may itself construct SentinelError when its
        # config-driven allowlist gets misused.
        from engine.policy.redaction import redact

        payload: dict[str, Any] = {
            "type": "error",
            "code": self.code,
            "exit_code": self.exit_code,
            "message": self.message,
            "suggested_fix": self.suggested_fix,
            "context": self.technical_context,
        }
        redacted = redact(payload)
        # `redact` returns the same shape it received; the dict cast keeps
        # mypy happy without changing runtime behavior.
        assert isinstance(redacted, dict)
        return redacted


# ---------------------------------------------------------------------------
# Configuration errors (exit code 2)
# ---------------------------------------------------------------------------


class ConfigError(SentinelError):
    """Any failure to load or validate `sentinel.config.yaml`."""

    DEFAULT_CODE = "E-CFG-002"


class ConfigFileNotFoundError(ConfigError):
    """The config file does not exist or is unreadable."""

    DEFAULT_CODE = "E-CFG-001"


class ConfigSchemaError(ConfigError):
    """The config parsed but failed schema validation."""

    DEFAULT_CODE = "E-CFG-002"


class ConfigSecretInlineError(ConfigError):
    """A secret was inlined where only an env-var reference is allowed."""

    DEFAULT_CODE = "E-CFG-003"


# ---------------------------------------------------------------------------
# Safety errors (exit code 4)
# ---------------------------------------------------------------------------


class UnsafeTargetError(SentinelError):
    """Generic safety-boundary rejection."""

    DEFAULT_CODE = "E-SAFE-001"


class UnknownHostError(UnsafeTargetError):
    """Host not in target allowlist and not local."""

    DEFAULT_CODE = "E-SAFE-001"


class DestructiveWithoutProofError(UnsafeTargetError):
    """Destructive mode requested without proof-of-authorization."""

    DEFAULT_CODE = "E-SAFE-002"


class ForbiddenFlagError(UnsafeTargetError):
    """A stealth/evasion/bypass flag was requested."""

    DEFAULT_CODE = "E-SAFE-003"


# ---------------------------------------------------------------------------
# Dependency / runtime errors
# ---------------------------------------------------------------------------


class DependencyMissingError(SentinelError):
    """A required external dependency is missing."""

    DEFAULT_CODE = "E-DEP-001"


class TestExecutionError(SentinelError):
    """Generic non-fatal failure inside the test runner (exit code 6)."""

    DEFAULT_CODE = "E-RUN-001"


class QualityGateFailedError(SentinelError):
    """Findings cleared the run but failed policy gates (exit code 1)."""

    DEFAULT_CODE = "E-QGATE-001"


class InternalError(SentinelError):
    """Catch-all for uncategorized programmer-fault failures (exit code 7)."""

    DEFAULT_CODE = "E-INT-001"

    def __init__(
        self,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, exit_code=EXIT_INTERNAL_ERROR, **kwargs)


class PluginError(SentinelError):
    """Failure originating in a plugin.

    Exit code depends on whether the plugin failed to load (5, treated as a
    missing dependency from the host's POV) or crashed at runtime (7).
    """

    DEFAULT_CODE = "E-PLG-001"


# ---------------------------------------------------------------------------
# LLM adapter errors (Phase 30, ADR-0042)
# ---------------------------------------------------------------------------


class LlmError(SentinelError):
    """Base class for LLM-provider errors.

    Concrete subclasses bind to the E-LLM-001..009 grid in
    :data:`engine.errors.codes.ERROR_REGISTRY`. The lifecycle catches
    ``LlmError`` and falls back to the deterministic path; the run still
    completes. The error code surfaces on the next ``audit.log`` line for
    debuggability.
    """

    DEFAULT_CODE = "E-LLM-004"


class LlmMissingKeyError(LlmError):
    """The configured ``api_key_env`` is unset."""

    DEFAULT_CODE = "E-LLM-001"


class LlmModelUnavailableError(LlmError):
    """The configured model is unknown / unreachable for this provider."""

    DEFAULT_CODE = "E-LLM-002"


class LlmBudgetExceededError(LlmError):
    """The per-run cost cap would be breached by this call."""

    DEFAULT_CODE = "E-LLM-003"


class LlmRequestRejectedError(LlmError):
    """The provider rejected the request (4xx other than 401/429)."""

    DEFAULT_CODE = "E-LLM-004"


class LlmResponseValidationError(LlmError):
    """The provider's response did not match the locked structured envelope."""

    DEFAULT_CODE = "E-LLM-005"


class LlmTimeoutError(LlmError):
    """The provider did not respond within the configured timeout."""

    DEFAULT_CODE = "E-LLM-006"


class LlmRateLimitedError(LlmError):
    """The provider returned 429 (or the local token-bucket denied the call)."""

    DEFAULT_CODE = "E-LLM-007"


class LlmSchemaMismatchError(LlmError):
    """Caller's response_schema rejected the otherwise-valid response."""

    DEFAULT_CODE = "E-LLM-008"


class LlmStructuredOutputUnsupportedError(LlmError):
    """The selected model / provider combination cannot honor structured output."""

    DEFAULT_CODE = "E-LLM-009"


# ---------------------------------------------------------------------------
# Browser-authenticated audit / vault errors (Phase 31, ADR-0043)
# ---------------------------------------------------------------------------


class AuthError(SentinelError):
    """Base class for browser-authenticated audit / vault failures.

    Concrete subclasses bind to the E-AUTH-001..006 grid in
    :data:`engine.errors.codes.ERROR_REGISTRY`. The orchestrator catches
    :class:`AuthError` at the lifecycle boundary; a vault failure aborts
    the run because running an authenticated audit without the session is
    a different audit than the operator asked for.
    """

    DEFAULT_CODE = "E-AUTH-001"


class VaultEntryNotFoundError(AuthError):
    """No vault entry matches the requested (host, name) pair."""

    DEFAULT_CODE = "E-AUTH-001"


class VaultEntryExpiredError(AuthError):
    """The vault entry's ``expires_at`` has passed."""

    DEFAULT_CODE = "E-AUTH-002"


class VaultHostMismatchError(AuthError):
    """The vault entry's recorded host does not match the active target host."""

    DEFAULT_CODE = "E-AUTH-003"


class VaultIntegrityError(AuthError):
    """Decryption / AEAD tag verification failed for the vault entry."""

    DEFAULT_CODE = "E-AUTH-004"


class LoginOriginChangedError(AuthError):
    """Login flow landed on a different origin than the start URL."""

    DEFAULT_CODE = "E-AUTH-005"


class AuthCommandForbiddenInCiError(AuthError):
    """Interactive `sentinel auth` subcommand invoked in CI mode."""

    DEFAULT_CODE = "E-AUTH-006"


__all__ = [
    "SentinelError",
    "ConfigError",
    "ConfigFileNotFoundError",
    "ConfigSchemaError",
    "ConfigSecretInlineError",
    "UnsafeTargetError",
    "UnknownHostError",
    "DestructiveWithoutProofError",
    "ForbiddenFlagError",
    "DependencyMissingError",
    "TestExecutionError",
    "QualityGateFailedError",
    "InternalError",
    "PluginError",
    "LlmError",
    "LlmMissingKeyError",
    "LlmModelUnavailableError",
    "LlmBudgetExceededError",
    "LlmRequestRejectedError",
    "LlmResponseValidationError",
    "LlmTimeoutError",
    "LlmRateLimitedError",
    "LlmSchemaMismatchError",
    "LlmStructuredOutputUnsupportedError",
    "AuthError",
    "VaultEntryNotFoundError",
    "VaultEntryExpiredError",
    "VaultHostMismatchError",
    "VaultIntegrityError",
    "LoginOriginChangedError",
    "AuthCommandForbiddenInCiError",
]
