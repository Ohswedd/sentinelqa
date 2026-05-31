# Public release announcement — draft

Status: `Stable`

Authority: `plans/phase-35-public-release/08-go-public.md`.

This file is the **owner's** draft copy for announcing the
public-release of `SentinelQA`. The agent does not publish it; the
owner adapts it to the channel (GitHub release notes, X/Twitter,
Mastodon, blog, Hacker News) and posts it after the visibility flip.

The drafts here intentionally avoid hyperbole. SentinelQA's whole
purpose is to answer one question with evidence — so the
announcement leads with that, not with adjectives.

## A. GitHub release notes for `v0.7.0`

````markdown
## SentinelQA v0.7.0 — public release

SentinelQA is a Playwright-native release-confidence engine for
LLM-built and human-built software. It crawls your app, generates
Playwright tests, runs them locally or in Docker, categorizes
failures with root-cause hypotheses, and turns the result into one
reproducible score plus an explainable release decision — backed by
evidence on disk, not opinions.

### What v0.7.0 ships

- **Engine**: discovery → planner → generator → runner → analyzer.
- **Modules**: functional, accessibility (axe + deterministic checks),
  performance (synthetic budgets, labeled), security (safe, allowlist-
  enforced), API contract, visual regression, chaos, LLM-code audit.
- **Supply chain**: CycloneDX SBOM, OSV lookup, freshness,
  postinstall scan, license audit.
- **Compliance packs**: WCAG 2.2 / GDPR-baseline / CCPA-baseline /
  SOC 2 audit-trail. Automated checks only — never legal claims.
- **Python SDK**: `Sentinel`, `AuditResult`, `Finding`, `TestPlan`.
  Snapshot-tested public surface.
- **MCP server**: twelve `sentinel.*` tools for agent integration.
- **CI**: GitHub Actions + GitLab CI templates; PR comment poster.

### Safety boundary (read this)

SentinelQA is for **authorized testing only**. The product refuses to
scan public targets that are not on its allowlist. No stealth. No
CAPTCHA bypass. No fingerprint evasion. No destructive defaults.
See [SECURITY.md](https://github.com/Ohswedd/sentinelqa/blob/main/SECURITY.md) and `CLAUDE.md` §6.

### Get started

```bash
uv pip install sentinelqa-cli
sentinel init
sentinel audit --url http://localhost:3000
```
````

Docs: <https://docs.sentinelqa.dev>.

### Pre-1.0

This is `v0.7.0`. Breaking changes between minor versions are
documented in [CHANGELOG.md](https://github.com/Ohswedd/sentinelqa/blob/main/CHANGELOG.md) with a migration path.
The road to `v1.0.0` runs through Phase 36 (PyPI / npm / Docker Hub
publish + the publish runbook). See
[docs/dev/semver.md](https://github.com/Ohswedd/sentinelqa/blob/main/docs/dev/semver.md).

### Thanks

Built by Ohswedd. Findings, evidence, and the safety boundary are
the work product; the project is Apache-2.0.

````

## B. Short post (X / Mastodon / Bluesky — ≤ 280 chars)

```text
SentinelQA v0.7.0 is public.

A Playwright-native release-confidence engine for LLM-built apps.
Crawl → plan → run → analyze → score, with evidence on disk and a
hard safety boundary (no stealth, no evasion, no unauthorized
targets).

Apache-2.0 · https://github.com/Ohswedd/sentinelqa
````

## C. Hacker News / Lobsters submission

Title:

```text
Show HN: SentinelQA — release-confidence engine for LLM-built apps
```

Body:

```markdown
Hi HN — I'm releasing SentinelQA, a Playwright-native
release-confidence engine targeted at the failure modes you see in
LLM-generated apps (dead buttons, fake routes, mocked data shipped,
frontend-only auth, missing CRUD edges, broken generated clients,
admin UI without authorization checks).

It's structured as a pipeline: discovery → planner → generator →
runner → analyzer. The planner is deterministic-first with optional
LLM proposals behind a versioned, budgeted adapter. The runner
shells out to Playwright locally or in a pinned Docker image. The
analyzer categorizes failures (app vs test vs env vs flake), emits
a root-cause hypothesis, and proposes a repro spec. Findings are
evidence-backed (artifact paths, redacted snippets, run ids) and
the quality score is reproducible from the persisted state.

Hard safety boundary: it refuses to scan public targets that aren't
on its allowlist. No stealth, no CAPTCHA bypass, no fingerprint
evasion, no destructive defaults. The full safety policy is in
CLAUDE.md §6.

It's pre-1.0 (v0.7.0 today); the MVP (Phases 00–29) is feature-
complete on `main` and Phases 30–36 land multi-provider LLMs,
browser-authenticated audits, extended security skills, supply-chain
audit, compliance packs, public release engineering, and the
PyPI/npm/Docker Hub publish workflow. Each phase ships with a signed
gate-review row in plans/STATUS.md.

Repo: https://github.com/Ohswedd/sentinelqa
Docs: https://docs.sentinelqa.dev
License: Apache-2.0
```

## D. Blog post (longer-form — adapt for `docs.sentinelqa.dev/blog/`)

```markdown
## SentinelQA: answering one question with evidence

> Can this software be trusted enough to ship?

SentinelQA exists to answer that question — for the LLM-built apps
that ship faster than humans can manually QA them, and for the
human-built apps that need a defensible quality bar in CI.

[...] adapt for chosen blog channel.
```

## Internal review

Before publishing any of these:

1. The owner re-reads the safety-boundary callout. The language
   ("authorized testing only", "no stealth", "no evasion") is
   non-negotiable per CLAUDE.md §6.
2. The owner removes the placeholder `Built by Ohswedd` line if a
   pseudonym or different attribution is preferred.
3. The owner double-checks the URLs resolve (especially
   `docs.sentinelqa.dev` — confirm the docs deploy ran post-flip).

The agent does NOT post these. Posting is owner-driven and lives
outside the agent's authorization scope.
