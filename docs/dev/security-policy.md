# Security policy (operator reference)

Status: `Stable`

Authority: `SECURITY.md` (public disclosure path),
our engineering rules(Safety boundary), §33 (Logging and secrets),
.

`SECURITY.md` is the **public** entrypoint — that's where reporters
land. This file is the **operator** runbook: how SentinelQA receives,
triages, and ships fixes for security issues, plus the supported-
versions matrix.

## Supported versions

| Stream    | Supported until            | Notes                                                                                      |
| --------- | -------------------------- | ------------------------------------------------------------------------------------------ |
| `0.7.x`   | next minor ships (`0.8.0`) | Current pre-1.0 stream.                                                                    |
| `< 0.7.0` | unsupported                | Pre-1.0 releases supersede each other; upgrade to the latest minor (`docs/dev/semver.md`). |

Once `v1.0.0` ships (Phase 36), SentinelQA switches to **latest two
minors only** — i.e. when `1.2.0` ships, `1.0.x` becomes unsupported
and `1.1.x` continues to receive security patches until `1.3.0`.

## Severity rating

We use **CVSS v4.0** (NIST NVD scoring). The first.qualitative band drives release urgency:

| Severity | CVSS v4.0 | Patch target   | Examples                                                                                                   |
| -------- | --------- | -------------- | ---------------------------------------------------------------------------------------------------------- |
| Critical | 9.0–10.0  | within 7 days  | Safety-boundary breach (stealth / evasion path), RCE, auth bypass on the audit CLI.                        |
| High     | 7.0–8.9   | within 30 days | Sensitive data exposure, unauthenticated access to audit artifacts, scoped privilege escalation.           |
| Medium   | 4.0–6.9   | within 60 days | Logic bugs in the safety policy, partial-redaction misses, supply-chain advisories without active exploit. |
| Low      | 0.1–3.9   | within 90 days | Hardening opportunities (header tightening, error-message verbosity), ergonomics.                          |

## Coordinated disclosure timeline

Reproduced from `SECURITY.md` for the operator's convenience:

|   Day | Milestone                                                                                   |
| ----: | ------------------------------------------------------------------------------------------- |
|     0 | Report received. Acknowledgement within 3 business days.                                    |
|  0–14 | Triage, CVSS, reproduction.                                                                 |
| 14–60 | Fix developed; regression tests added; ADR opened if the safety boundary changed.           |
| 60–80 | Patch release prepared; reporter reviews the fix.                                           |
| 80–90 | Coordinated publication: tag, GitHub Security Advisory, reporter credit (unless anonymous). |

If we cannot meet the 90-day deadline, we coordinate an embargo
extension in writing with the reporter.

## Embargo + advisory publication

1. The fix lands on a private fork or in a draft GHSA — never on `main` before publication.
2. A regression test that proves the fix lands in the same PR .
3. When the embargo lifts, the GHSA is published, the patch release is tagged via `docs/release/pre-1.0-review.md`, `CHANGELOG.md` gets a `### Security` section under that release, and the reporter is credited.

## Dependabot

`.github/dependabot.yml` (Phase 35.07) covers four ecosystems on a
weekly cadence:

| Ecosystem          | Manifests watched                                                | Notes                                                                          |
| ------------------ | ---------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `pip` (Python)     | `/`, `/apps/cli`, `/packages/python-sdk`, `/packages/mcp-server` | Per-package so workspace-scoped upgrades surface separately.                   |
| `npm` (JavaScript) | `/`, `/packages/ts-runtime`                                      | Root reads pnpm-lock; the ts-runtime entry surfaces workspace-scoped upgrades. |
| `github-actions`   | `/`                                                              | Weekly; catches upstream action advisories.                                    |
| `docker`           | `/apps/cli/sentinel/runner/docker`                               | The Playwright runner base image.                                              |

Minor + patch upgrades are grouped per ecosystem to keep the PR
queue manageable. Major upgrades arrive as their own PRs so the
owner reviews each one explicitly.

## Private vulnerability reporting

After the public flip (task 35.08) the owner enables GitHub Private
Vulnerability Reporting in
`Settings → Code security and analysis → Private vulnerability reporting → Enable`.
That setting cannot be configured on a private repo before the flip.

## Runbook for the on-call

1. New report arrives via GHSA or `security@sentinelqa.dev`.
2. Acknowledge within 3 business days.
3. Triage: reproduce, score (CVSS v4.0), file an internal tracker issue with severity + supported-versions impact.
4. Fix on a feature branch named `security/<short-slug>`. Tests first, then the fix.
5. Open a draft GHSA — never a public PR — for the patch. Use the `cve` field if a CVE has been minted.
6. Coordinate disclosure with the reporter; agree on a publication date inside the 90-day window (sooner for criticals).
7. Tag the patch release per `docs/release/pre-1.0-review.md`, publish the GHSA, update `CHANGELOG.md`, post the deprecation notice on the docs site.
8. If the safety boundary was touched, open an ADR (`docs/adr/_template.md`) before the publication date.

## Related

- [`SECURITY.md`](../../SECURITY.md) — public disclosure path.
- [`docs/dev/semver.md`](./semver.md) — supported-versions policy.
- [`docs/release/pre-1.0-review.md`](../release/pre-1.0-review.md) — pre-tag review the owner signs.
- [`.github/dependabot.yml`](../../.github/dependabot.yml) — Dependabot config.
- [](../../) — task spec.
