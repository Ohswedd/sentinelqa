# ADR-0030: Integrations — stdlib HTTP adapters, off-by-default, redacted

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

the documentation reserves `integrations/` for adapters that wire SentinelQA
to external services. (ADR-0022) shipped the GitHub /
GitLab CI surface (composite Action, reusable workflow, PR / MR
posters). (this ADR) lights up the rest: BrowserStack and
Sauce Labs (remote runners), Slack (notifications), GitHub deeper
integration (commit statuses + issue creation), GitLab deeper
integration (commit statuses), and Jira / Linear issue creation.

The design must honour three constraints:

1. **our engineering rules(Dependency rules).** No new runtime dependencies; the posters proved stdlib `urllib` works.
2. **our engineering rules(Logging and secrets) / §41 (Privacy).** Every adapter reads credentials from environment variables at call time, never logs them, and never persists them.
3. **our engineering rules(Architecture rules).** The engine MUST NOT import these adapters directly — they live behind the SDK plugin Protocols (`sentinelqa.plugins`) or are invoked via CLI / external workflow callers.

## Decision

A single shared HTTP helper, plus per-service modules.

- **Shared client.** `integrations/_http.py` exposes `HttpClient` (stdlib `urllib` only), `AuthHeader` (Bearer / Basic / custom-name factory class methods), `RetrySpec` (exponential backoff on `{429, 502, 503, 504}` honoring `Retry-After`), and `redact_url` / `safe_reason` helpers. Every adapter uses this client so retry, redaction, and timeout behaviour are identical across services. JSON requests and plain-text replies are both supported (Slack returns `"ok"`).
- **BrowserStack and Sauce Labs.** Each ships as a class shaped like the SDK `RunnerPlugin` Protocol (kind / name / version / capabilities / permissions / `run(invocation, context)`). Credentials live in dedicated env vars (`BROWSERSTACK_USERNAME` / `BROWSERSTACK_ACCESS_KEY`; `SAUCE_USERNAME` / `SAUCE_ACCESS_KEY`). Capability mappers are pure functions over the SentinelQA-shaped invocation. HTTP 429 quota errors return `status="quota_exceeded"` in the outcome dict so callers can fall back to the local runner — never crash the run.
- **Slack.** `integrations.slack.SlackPoster` reuses the Block Kit payload. The webhook URL is read from `SLACK_WEBHOOK_URL` at call time. A small on-disk dedup cache (sha256 of `webhook host + payload`, 5-minute window) suppresses double-posts when CI re-runs. The CLI entry is `python -m integrations.slack.poster --payload <file>`; `sentinel report --notify slack` calls the same helper.
- **GitHub deeper.** `integrations.github.status.post_commit_status` posts a single commit status (`pending|success|failure|error`), with a 140-char clamp on `description`. The `post_pr_comment.py` keeps owning PR comments; this module only adds the commit-status surface that branch protection watches. `integrations.github.issue.create_issue_for_finding` opens (or upserts via a `[sentinelqa:FND-XXX]` anchor in the title) an issue. **Auto-create is off by default**: the caller must pass `auto_create=True` AND set `policy.github.auto_create_issue: true`. Issue bodies pass through `engine.policy.redaction.redact` so credentials never reach GitHub.
- **GitLab deeper.** `integrations.gitlab.status.post_commit_status` posts a pipeline commit status (`pending|running|success|failed|
canceled`) with a 255-char `description` clamp and a default `name="sentinelqa/quality-gate"`. Project paths are URL-encoded so `group/sub/repo` works without caller-side encoding.
- **Jira and Linear.** Adapters expose `create_issue(finding) -> issue_url`. Both require an explicit project key / team id and HTTPS base URLs (Linear hardcodes the API endpoint). Severity-to-priority mappings are fixed: critical → Highest / Urgent; high → High / 2; medium → Medium / 3; low → Low / 4; info → Lowest / 0. Findings are redacted before description rendering.
- **Config blocks.** `policy.github.auto_create_issue: bool` and `policy.integrations.{slack, jira, linear}` cover the new feature gates. Every block defaults off; the example config documents them with commented-out values so users opt in consciously.
- **Credential-leak guard.** `tests/integration/integrations/test_credential_leak_guard.py` runs on every CI pass and FAILS if any secret env var is set (`BROWSERSTACK_USERNAME/_ACCESS_KEY`, `SAUCE_USERNAME/_ACCESS_KEY`, `SLACK_WEBHOOK_URL`, `JIRA_USER_EMAIL/_API_TOKEN`, `LINEAR_API_KEY`). `GITHUB_TOKEN` is explicitly excluded because the same CI lane uses it to post the Phase-17 PR comment.

## Consequences

- **Positive:** - Single retry / redaction surface across seven services — bug fixes apply uniformly. - No new runtime deps; the production wheel remains pure stdlib - Pydantic + Pillow + Jinja2. - Every adapter is unit-testable without network access via a `HttpClient` subclass. - Adapters defer to existing plugin patterns (kind / name / version / capabilities / permissions), so any of them can be packaged as a third-party plugin later without code change.
- **Negative / trade-off:** - `HttpClient` is hand-rolled, not `requests` or `httpx`. Future edge cases (HTTP/2, streaming responses, advanced cookie handling) would need a deliberate migration if we ever need them. None of the integrations require those features. - Auto-issue creation in GitHub / Jira / Linear is documented but un-wired into the audit lifecycle. A future ADR is required before any module starts opening issues on its own.
- **Follow-up obligations:** - (Docs & ADRs) documents end-to-end setup for each adapter, including the manual-verification step (real-provider smoke runs). - (Versioning & Release Prep) reviews whether any of these adapters should be split into their own pyproject members ahead of the first PyPI cut.

## Alternatives considered

- **Pull `requests` into the dev / runtime dependency set.** Rejected: our engineering rules("Do not add large frameworks for small utilities"). The stdlib pattern is already proven by the posters and we keep the wheel footprint small.
- **Wire BrowserStack / Sauce Labs into `sentinel audit` directly.** Rejected: it would couple the engine to remote-runner billing surfaces and violate our engineering rules's adapter-boundary rule. The current shape (RunnerPlugin Protocol) lets operators opt in via config or plugin registration.
- **Wire issue creation into the audit lifecycle.** Rejected for this phase: issue creation has irreversible blast radius (you cannot un-open a Jira ticket). keeps the surface but forces an explicit opt-in.

## References

- the documentation (Repository structure), §21.4 ( CI surface), §21.5 ( integrations — added by this ADR), §22 (Plugin architecture).
- our engineering rules(Safety boundary), §7 (Architecture), §33 (Logging and secrets), §35 (Dependency rules), §41 (Privacy and telemetry).
- Related ADRs: ADR-0022 ( CI integration); ADR-0029 ( plugin architecture).
