# Security policy

SentinelQA takes security seriously. This document is the
**private-disclosure** path for reporting vulnerabilities in
SentinelQA itself and abuses of its safety boundary.

> **Public issues are not the disclosure channel.** Do not file a
> bug report or feature request for a security finding. Use one of
> the private channels below.

## Reporting a vulnerability

### Preferred — GitHub Private Vulnerability Reporting

File a draft advisory privately at:

<https://github.com/Ohswedd/sentinelqa/security/advisories/new>

This goes only to the project maintainers (the human owners listed in
[`.github/CODEOWNERS`](./.github/CODEOWNERS)). It does not create a
public issue.

### Alternative — email

If GitHub Private Vulnerability Reporting is unavailable, email:

**`security@sentinelqa.dev`**

Encrypted mail is preferred. The maintainer PGP fingerprint is published
alongside the v1.0.0 release.

## What to include

- A clear description of the issue and its impact.
- Reproduction steps (commands, config, redacted evidence).
- SentinelQA version and commit (`sentinel --version`).
- Whether the issue affects the safety boundary (stealth, evasion,
  unauthorized targets, destructive defaults).
- Suggested remediation, if you have one.

Please **redact secrets** (tokens, cookies, customer data) before
including any artifact.

## Coordinated disclosure timeline

SentinelQA follows a **90-day coordinated disclosure** policy
(industry standard, modeled on Google Project Zero).

|   Day | Milestone                                                                                                                                |
| ----: | ---------------------------------------------------------------------------------------------------------------------------------------- |
|     0 | Report received. Acknowledgement within 3 business days.                                                                                 |
|  0–14 | Triage, severity assessment (CVSS v4.0), reproduction.                                                                                   |
| 14–60 | Fix developed, regression tests added, ADR opened if the safety boundary changed.                                                        |
| 60–80 | Release prepared (patch version per [`docs/dev/semver.md`](./docs/dev/semver.md)). Reporter reviews the fix.                             |
| 80–90 | Coordinated publication: release tagged, GitHub Security Advisory published, reporter credited (unless they prefer to remain anonymous). |

If we cannot meet the 90-day deadline, we will coordinate an embargo
extension in writing with the reporter.

## Supported versions

| Version | Supported | Notes                                                                          |
| ------- | --------- | ------------------------------------------------------------------------------ |
| `1.0.x` | Yes       | Current stable.                                                                |
| `0.x`   | No        | Pre-1.0 releases supersede each other; upgrade to the latest minor or `1.0.x`. |

Once a `v2.0.0` ships, SentinelQA follows a **"latest two minors"** support
window. See [`docs/dev/security-policy.md`](./docs/dev/security-policy.md).

## Severity ratings

Severity is rated via **CVSS v4.0** (NVD-style). Severity bands map
to release urgency:

| Severity | Response target      | Notes                                                     |
| -------- | -------------------- | --------------------------------------------------------- |
| Critical | patch within 7 days  | Safety boundary breach, RCE, auth bypass.                 |
| High     | patch within 30 days | Sensitive data exposure, scoped privilege escalation.     |
| Medium   | patch within 60 days | Logic bugs, supply-chain concerns without active exploit. |
| Low      | patch within 90 days | Hardening opportunities, ergonomics.                      |

## Scope

In scope:

- The SentinelQA CLI, Python SDK, MCP server, and TypeScript runtime.
- Generated tests when they leak secrets or violate the safety
  boundary in ways that originate in our generator.
- The Docker runner image we publish.
- The `sentinelqa-cli` and `sentinelqa` PyPI packages and the
  `@sentinelqa/*` npm packages.
- The docs site at `docs.sentinelqa.dev`.

Out of scope (please do not test against):

- Third-party services SentinelQA integrates with
  (BrowserStack, Sauce Labs, Slack, Jira, Linear, GitHub). Report
  those upstream.
- Public targets that are not your own and that have not authorized
  SentinelQA testing. Scanning targets without authorization violates
  the safety boundary; it is not a finding against SentinelQA, it is a
  misuse of SentinelQA.

## Safe harbor

We will not pursue or support legal action against researchers who:

- Report findings in good faith via the private channels above.
- Make a good-faith effort to avoid privacy violations, destruction of
  data, and interruption of service.
- Stay within the scope above.

## Hall of fame

Reporters who follow the coordinated-disclosure process will be
credited (or anonymously credited at their option) in the GitHub
Security Advisory for each issue and in `CHANGELOG.md` under the
release that ships the fix.

## Last reviewed

`2026-06-01`. This policy is reviewed at every minor release.
