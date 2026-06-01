# Trademarks and naming

Status: `Stable`

.md` §40 (Versioning & release rules — package contents inspected pre-release),.

This is the trademark verdict for the product name **"SentinelQA"**. Until either verdict here changes, the name is cleared for **internal** use (the private monorepo, internal documentation, working-group conversation, this CI). Public publication (PyPI / npm / Docker Hub / dedicated domain / marketing) requires the human owner to complete the registered-marks search rows below before tagging the first release per `docs/dev/semver.md`.

## Verdicts at a glance

| Search lane                                          | Verdict                   | As of      | Performed by     | Notes                                                                                                                                                                                                                                                                                                                        |
| ---------------------------------------------------- | ------------------------- | ---------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PyPI registry                                        | **Clear**                 | 2026-05-30 | verdict commit   | `https://pypi.org/simple/sentinelqa/` returned HTTP 404; no package named `sentinelqa` is published.                                                                                                                                                                                                                         |
| npm registry (unscoped)                              | **Clear**                 | 2026-05-30 | verdict commit   | `https://registry.npmjs.org/sentinelqa` returned HTTP 404; no package named `sentinelqa` is published.                                                                                                                                                                                                                       |
| npm registry (`@sentinelqa/*` scope)                 | **Clear**                 | 2026-05-30 | verdict commit   | `https://registry.npmjs.org/@sentinelqa/ts-runtime` returned HTTP 404; scope unclaimed.                                                                                                                                                                                                                                      |
| GitHub project name (`site:github.com "SentinelQA"`) | **Clear**                 | 2026-05-30 | verdict commit   | No public GitHub repository named "SentinelQA" returned by site-scoped web search. Adjacent-but-distinct projects (Azure Sentinel, SentinelOne, sentinel-official, sentinel-hub, alienator88/Sentinel, SentineLabs, nintexplatform/sentinel) are in security or apparently unrelated domains and do not use the "QA" suffix. |
| General web common-law usage                         | **Clear**                 | 2026-05-30 | verdict commit   | A targeted web search for `"SentinelQA"` returned no project, company, or product literally using that name.                                                                                                                                                                                                                 |
| USPTO registered-marks search (US)                   | **AWAITING owner action** | _pending_  | Human owner only | The USPTO TM search at <https://tmsearch.uspto.gov/> requires an interactive session that this loop cannot drive. Must be completed manually before tagging v0.7.0+ (`docs/dev/semver.md`).                                                                                                                                  |
| EUIPO TMview search (EU)                             | **AWAITING owner action** | _pending_  | Human owner only | Run the search at <https://www.tmview.tmdn.org/>. Same blocker as USPTO.                                                                                                                                                                                                                                                     |
| UKIPO mark search (UK)                               | **AWAITING owner action** | _pending_  | Human owner only | Run the search at <https://www.gov.uk/search-for-trademark>. Same blocker.                                                                                                                                                                                                                                                   |

The three registered-marks lanes are not deferred scope — they are **owner-only** actions that must clear before the first public release, and they are captured as explicit pre-tag blockers in the pre-tag review process.

## Adjacent-name landscape (informational)

These names appeared in the common-law sweep and are documented here so a future PR cannot drift into them by accident:

- **SentinelOne** — endpoint protection / cybersecurity vendor. Registered marks in multiple classes. SentinelQA differs by name (the trailing `QA` and the missing `One`) and by product space (test automation vs. endpoint protection); the human owner should still review the USPTO TESS / EUIPO classes for any overlap.
- **Azure Sentinel** — Microsoft SIEM. Distinct compound mark; not a single-word conflict.
- **sentinel-hub** — Sentinel satellite imagery community on GitHub. Distinct compound mark + domain.
- **sentinel-official**, **alienator88/Sentinel**, **nintexplatform/sentinel**, **SentineLabs** — open-source projects named "Sentinel" or close variants, in security or system-tools adjacent spaces. The product name we ship as the head of the brand is "SentinelQA", not "Sentinel" alone; that suffix is the differentiator and must be preserved.

If any of the adjacent-name owners files a "Sentinel + QA" mark before we publish, that is a clean trigger to revisit this verdict and propose an alternative.

## Source links audited

- PyPI: <https://pypi.org/simple/sentinelqa/>
- npm: <https://registry.npmjs.org/sentinelqa>, <https://registry.npmjs.org/@sentinelqa/ts-runtime>
- USPTO TM search (still authoritative as of 2026-05-30 — confirmed via <https://www.uspto.gov/trademarks/search>): <https://tmsearch.uspto.gov/>
- EUIPO TMview: <https://www.tmview.tmdn.org/>
- UKIPO mark search: <https://www.gov.uk/search-for-trademark>
- Targeted web search for "SentinelQA" returned no project- or company-named result.

## What changes the verdict

Any of the following invalidates this row and requires a re-verdict commit before publication:

1. A `sentinelqa` package appears on PyPI, npm, or any other registry SentinelQA plans to publish to.
2. A registered mark turns up in the USPTO / EUIPO / UKIPO searches once the owner runs them.
3. A common-law user emerges (a project that ships software under the literal name "SentinelQA" with prior use in the same product class).
4. A trademark dispute is filed against SentinelQA's name.

In any of those cases:

- Stop the pending tag ( blocker fires).
- Propose at least two alternative names in this doc and run the same lane sweep against them.
- Write an ADR named "ADR-NNNN: Product name re-clearance" recording the conflict, the alternatives considered, and the chosen replacement.
- Only after the ADR is Accepted may publication resume.

## What this clearance does NOT cover

- **Domain registrations.** No `sentinelqa.io` / `.com` / `.dev` was registered as part of this verdict. Domain availability must be checked at registration time.
- **Logo / visual identity.** SentinelQA has no logo yet; when one is designed, run a separate clearance for the visual mark.
- **Sub-product names.** Each major-feature codename (e.g. for a + cloud offering, an MCP server brand) must be re-cleared on its own.
- **Other jurisdictions.** The USPTO / EUIPO / UKIPO trio covers the markets the owner currently plans for. Additional markets (CA, AU, JP, IN, …) require their own searches before launching there.

## Internal-only use is still safe

This verdict explicitly says: continued use of "SentinelQA" inside this private repository, in the working group, in this CI's commit messages and PR titles, and in this monorepo's `pyproject.toml` / `package.json` `name` fields is fine. What it does NOT permit is:

- Publishing a package literally named `sentinelqa` (or `@sentinelqa/*`) to PyPI / npm / Docker Hub / etc.
- Registering a public domain matching `sentinelqa.*`.
- Filing for a trademark.
- Issuing public marketing under the SentinelQA name.

Those steps unlock once the registered-marks rows above are signed off by the human owner in this file _and_ in the pre-tag review process.
