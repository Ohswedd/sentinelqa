"""Single source of truth for SentinelQA error codes and CLI exit codes.

Each entry binds:

- A symbolic ``code`` (e.g. ``"E-CFG-001"``) used by `to_agent_message` and
  the docs site (Phase 27).
- A CLI ``exit_code`` int matching PRD §13.2 / CLAUDE.md §13.
- A default ``message`` template and ``suggested_fix`` rendered when the
  exception is raised without explicit arguments.

The CLI exit-code constants are mirrored in :mod:`engine.policy.exit_codes`
for consumers that only need the numbers (no error import needed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Exit-code constants. Match PRD §13.2 (updated in Phase 01) and CLAUDE.md §13.
EXIT_SUCCESS: Final[int] = 0
EXIT_QUALITY_GATE_FAILED: Final[int] = 1
EXIT_CONFIG_ERROR: Final[int] = 2
EXIT_RUNTIME_ERROR: Final[int] = 3
EXIT_UNSAFE_TARGET: Final[int] = 4
EXIT_DEPENDENCY_MISSING: Final[int] = 5
EXIT_TEST_EXECUTION_FAILED: Final[int] = 6
EXIT_INTERNAL_ERROR: Final[int] = 7


@dataclass(frozen=True, slots=True)
class ErrorCodeSpec:
    """Static description of a SentinelQA error code."""

    code: str
    exit_code: int
    message_template: str
    suggested_fix: str


# Registry. Keyed by the symbolic code. Adding a new entry is intentionally
# verbose so the reviewer sees the exit-code mapping at the diff level.
ERROR_REGISTRY: Final[dict[str, ErrorCodeSpec]] = {
    "E-CFG-001": ErrorCodeSpec(
        code="E-CFG-001",
        exit_code=EXIT_CONFIG_ERROR,
        message_template="Configuration file is missing or unreadable: {path}",
        suggested_fix=(
            "Create `sentinel.config.yaml` at the project root or pass "
            "`--config <path>` pointing at an existing file."
        ),
    ),
    "E-CFG-002": ErrorCodeSpec(
        code="E-CFG-002",
        exit_code=EXIT_CONFIG_ERROR,
        message_template="Configuration failed schema validation: {detail}",
        suggested_fix=(
            "Run `sentinel doctor` for a precise diff against the expected " "schema (PRD §17.1)."
        ),
    ),
    "E-CFG-003": ErrorCodeSpec(
        code="E-CFG-003",
        exit_code=EXIT_CONFIG_ERROR,
        message_template=(
            "Inline secret detected at config key {field!r}; secrets must "
            "come from environment variables."
        ),
        suggested_fix=(
            "Replace the literal value with the corresponding `*_env` key "
            "(e.g. `password_env: TEST_USER_PASSWORD`)."
        ),
    ),
    "E-SAFE-001": ErrorCodeSpec(
        code="E-SAFE-001",
        exit_code=EXIT_UNSAFE_TARGET,
        message_template=("Host {host!r} is not in target.allowed_hosts and is not local."),
        suggested_fix=(
            "Add the host to `target.allowed_hosts` only if you own or are "
            "authorized to test it. SentinelQA never permits unauthorized "
            "scans (PRD §2, CLAUDE.md §6)."
        ),
    ),
    "E-SAFE-002": ErrorCodeSpec(
        code="E-SAFE-002",
        exit_code=EXIT_UNSAFE_TARGET,
        message_template=(
            "Destructive mode requested for {host!r} without a valid "
            "proof-of-authorization document."
        ),
        suggested_fix=(
            "Provide `target.proof_of_authorization` pointing at a signed "
            "doc that covers this host, actor, and scope, and is not expired."
        ),
    ),
    "E-SAFE-003": ErrorCodeSpec(
        code="E-SAFE-003",
        exit_code=EXIT_UNSAFE_TARGET,
        message_template=(
            "Forbidden CLI flag {flag!r} requested; "
            "stealth/evasion/bypass features are not part of SentinelQA."
        ),
        suggested_fix=(
            "Remove the flag. See PRD §2.1 and CLAUDE.md §6 for the full "
            "list of forbidden capabilities."
        ),
    ),
    "E-DEP-001": ErrorCodeSpec(
        code="E-DEP-001",
        exit_code=EXIT_DEPENDENCY_MISSING,
        message_template="Required dependency is missing: {dependency}",
        suggested_fix=(
            "Run `make install` (or `uv sync --frozen --all-packages` and "
            "`pnpm install --frozen-lockfile`) and retry."
        ),
    ),
    "E-RUN-001": ErrorCodeSpec(
        code="E-RUN-001",
        exit_code=EXIT_TEST_EXECUTION_FAILED,
        message_template="Test execution failed: {detail}",
        suggested_fix=(
            "Inspect the Playwright trace and stdout under "
            "`.sentinel/runs/<run-id>/` for the failing step."
        ),
    ),
    "E-QGATE-001": ErrorCodeSpec(
        code="E-QGATE-001",
        exit_code=EXIT_QUALITY_GATE_FAILED,
        message_template=("Quality gate failed: {detail}"),
        suggested_fix=(
            "Either fix the underlying findings or adjust `policy` in "
            "`sentinel.config.yaml` if the gate is genuinely too strict."
        ),
    ),
    "E-INT-001": ErrorCodeSpec(
        code="E-INT-001",
        exit_code=EXIT_INTERNAL_ERROR,
        message_template="Internal SentinelQA error: {detail}",
        suggested_fix=(
            "Re-run with `--verbose` and file a bug report including the "
            "captured stack trace; secrets are redacted by default."
        ),
    ),
    "E-PLG-001": ErrorCodeSpec(
        code="E-PLG-001",
        exit_code=EXIT_DEPENDENCY_MISSING,
        message_template="Plugin {plugin!r} could not be loaded: {detail}",
        suggested_fix=(
            "Verify the plugin is installed, declares the expected entry "
            "point, and matches the host SentinelQA version."
        ),
    ),
    "E-PLG-002": ErrorCodeSpec(
        code="E-PLG-002",
        exit_code=EXIT_INTERNAL_ERROR,
        message_template="Plugin {plugin!r} crashed at runtime: {detail}",
        suggested_fix=(
            "Disable the plugin via `modules.<name>: false` while you "
            "diagnose; SentinelQA core continues without it."
        ),
    ),
    # ------------------------------------------------------------------
    # LLM adapter errors (Phase 30, ADR-0042). Most LLM failures are
    # graceful — the caller falls back to the deterministic path. The
    # codes below surface when the user explicitly asked for an LLM
    # capability and the request cannot complete safely.
    # ------------------------------------------------------------------
    "E-LLM-001": ErrorCodeSpec(
        code="E-LLM-001",
        exit_code=EXIT_DEPENDENCY_MISSING,
        message_template=(
            "LLM provider {provider!r} is missing required credentials: env "
            "var {env_var!r} is not set."
        ),
        suggested_fix=(
            "Export the env var, or set `llm.providers.<name>.api_key_env` "
            "to a name that IS set. SentinelQA never accepts inline API keys."
        ),
    ),
    "E-LLM-002": ErrorCodeSpec(
        code="E-LLM-002",
        exit_code=EXIT_DEPENDENCY_MISSING,
        message_template=(
            "LLM provider {provider!r} cannot reach the configured model " "{model!r}: {detail}"
        ),
        suggested_fix=(
            "Confirm the model name is correct for this provider (see `sentinel "
            "llm list`). For local providers (Ollama), run `ollama pull <model>`."
        ),
    ),
    "E-LLM-003": ErrorCodeSpec(
        code="E-LLM-003",
        exit_code=EXIT_QUALITY_GATE_FAILED,
        message_template=(
            "LLM per-run cost budget exceeded: projected {projected_usd:.4f} "
            "USD > budget {budget_usd:.4f} USD."
        ),
        suggested_fix=(
            "Raise `llm.budget.max_usd_per_run`, lower `planner.llm.max_proposals`, "
            "or switch to a cheaper model. The deterministic path always works."
        ),
    ),
    "E-LLM-004": ErrorCodeSpec(
        code="E-LLM-004",
        exit_code=EXIT_RUNTIME_ERROR,
        message_template=(
            "LLM provider {provider!r} rejected the request: HTTP " "{status_code} {detail}"
        ),
        suggested_fix=(
            "Inspect the redacted request in the audit log. Common causes: "
            "model deprecated, region/account blocked, content filter."
        ),
    ),
    "E-LLM-005": ErrorCodeSpec(
        code="E-LLM-005",
        exit_code=EXIT_RUNTIME_ERROR,
        message_template=(
            "LLM provider {provider!r} returned a response that failed "
            "structured-output validation: {detail}"
        ),
        suggested_fix=(
            "The locked prompt envelope guards against this; if it recurs, "
            "switch to a model that supports structured output and re-run."
        ),
    ),
    "E-LLM-006": ErrorCodeSpec(
        code="E-LLM-006",
        exit_code=EXIT_RUNTIME_ERROR,
        message_template=("LLM provider {provider!r} timed out after {timeout_seconds:.1f}s."),
        suggested_fix=(
            "Raise `*.llm.request_timeout_seconds`, or switch to a faster "
            "provider. The deterministic fallback path always works."
        ),
    ),
    "E-LLM-007": ErrorCodeSpec(
        code="E-LLM-007",
        exit_code=EXIT_RUNTIME_ERROR,
        message_template=("LLM provider {provider!r} returned HTTP 429 (rate-limited)."),
        suggested_fix=(
            "Lower `llm.rate_limit.requests_per_minute`, retry later, or "
            "switch providers. The deterministic fallback path always works."
        ),
    ),
    "E-LLM-008": ErrorCodeSpec(
        code="E-LLM-008",
        exit_code=EXIT_RUNTIME_ERROR,
        message_template=(
            "LLM provider {provider!r} returned data that does not match the "
            "caller-side schema: {detail}"
        ),
        suggested_fix=(
            "Caller schema mismatches are a model-quality signal; the run "
            "drops the malformed response and continues deterministically."
        ),
    ),
    "E-LLM-009": ErrorCodeSpec(
        code="E-LLM-009",
        exit_code=EXIT_CONFIG_ERROR,
        message_template=(
            "LLM provider {provider!r} does not support structured output for " "model {model!r}."
        ),
        suggested_fix=(
            "Pick a model that supports structured output (see `sentinel llm "
            "list`) or disable the LLM feature for this caller."
        ),
    ),
}


def exit_code_for(code: str) -> int:
    """Return the CLI exit code bound to a symbolic error ``code``.

    Falls back to :data:`EXIT_RUNTIME_ERROR` if the code is not registered.
    The fallback is intentional: the CLI should always be able to exit, even
    if a caller invents a code not yet in the registry. Registered codes
    are the contract; unregistered ones are a bug to fix in code review.
    """

    spec = ERROR_REGISTRY.get(code)
    if spec is None:
        return EXIT_RUNTIME_ERROR
    return spec.exit_code


__all__ = [
    "EXIT_SUCCESS",
    "EXIT_QUALITY_GATE_FAILED",
    "EXIT_CONFIG_ERROR",
    "EXIT_RUNTIME_ERROR",
    "EXIT_UNSAFE_TARGET",
    "EXIT_DEPENDENCY_MISSING",
    "EXIT_TEST_EXECUTION_FAILED",
    "EXIT_INTERNAL_ERROR",
    "ErrorCodeSpec",
    "ERROR_REGISTRY",
    "exit_code_for",
]
