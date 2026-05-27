# Trademarks and naming

Status: `Planned`

## What's open

The product name **"SentinelQA"** has not been cleared for trademark conflicts. Before any public release (public repo, package upload, marketing copy, domain registration, conference talk, etc.) the human owner must:

1. Search the relevant trademark databases at minimum:
   - US: <https://tmsearch.uspto.gov/>
   - EU: <https://www.tmdn.org/tmview/>
   - UK: <https://www.gov.uk/search-for-trademark>
2. Search common-law usage in the software / QA tooling space (existing GitHub repos, npm packages, PyPI packages, conference programs).
3. Check domain availability and avoid registering a confusingly similar domain.
4. Record the findings in a new ADR ("ADR-NNNN: Product name clearance").
5. If a conflict is found, propose alternatives, repeat the check, and only proceed once the name is clear.

This is **Phase 28**'s responsibility (`plans/phase-28-versioning-release/05-trademark-check.md`). Until then, all uses of "SentinelQA" are internal to a private repository and the working group.

## Why this matters

A late-stage rename costs more than an early-stage one. Renaming after publication means renaming on PyPI, npm, GitHub, every doc page, every CI workflow, every example, and every external reference. Doing the clearance before the first public release keeps that cost zero.

## What to do in the meantime

- Continue to use "SentinelQA" in code, docs, and conversation.
- Do not register a public domain (e.g. `sentinelqa.io`) until clearance is done.
- Do not file for any trademark until clearance is done.
- Do not upload a package named `sentinelqa` to PyPI / npm until clearance is done. (The package metadata can declare the name internally; what we avoid is publishing it.)
