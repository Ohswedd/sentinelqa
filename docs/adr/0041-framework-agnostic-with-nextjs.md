# ADR-0041: Framework-agnostic crawler with first-class Next.js support

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

our product spec Open Question #8 asked whether the first target framework
should be Next.js only or framework-agnostic from day one. The
recommended answer was "framework-agnostic crawler, with first-class
Next.js support." Phase 05 (ADR-0010) shipped an HTTP-first crawler
that targets any web app; Phase 17 (ADR-0022) added the Playwright
backend for SPAs. Phase 26 (ADR-0031) ships demo apps in Next.js,
FastAPI, Django, Flask, and React + Vite, all auditable by the same
CLI with the same config schema.

This ADR is one of the eight Phase-27 open-question ADRs.

## Decision

**The crawler, planner, generator, and runner are framework-agnostic.**
Framework-specific heuristics live behind small, named helpers and
are layered on top of the generic core:

- **Discovery**: HTTP backend uses standard HTTP + BeautifulSoup + robots.txt; Playwright backend uses raw DOM + console events. Neither calls Next.js / Django / Flask APIs directly.
- **Diff-aware test selection (Phase 17)**: ships deterministic Next.js (App Router + Pages Router) and Vite heuristics for translating a git diff into impacted routes. Other frameworks fall back to the "broad-impact tripwire" path (run everything).
- **Examples**: five reference apps span Next.js / FastAPI / Django / Flask / Vite (Phase 26). The audit produces the same artifact tree for every framework.

**First-class Next.js** means: documented diff-aware selection
heuristics, an example app, a tested LLM-broken Next.js fixture, and
the quickstart that uses the Next.js demo. It does **not** mean
Next.js-only code paths in the core.

## Consequences

- **Positive:** the core stays usable for any web framework, including ones we haven't tested yet. Adopters bring their stack and the audit works.
- **Positive:** Next.js gets a polished experience without holding other frameworks back — the framework-specific code is small and isolated.
- **Negative / trade-off:** diff-aware test selection is less precise for frameworks without dedicated heuristics. Acceptable — the fallback runs everything; precision is an additive optimization, not a correctness requirement.
- **Negative / trade-off:** more frameworks to keep working as the PRD evolves. Mitigated by the Phase 26 example-app structural tests (`tests/integration/examples/`).
- **Follow-up obligations:** when new frameworks get tested against (e.g. Remix, SvelteKit, Astro itself), add example apps and diff-aware heuristics behind the same pattern.

## Alternatives considered

- **Next.js-only MVP.** Rejected — narrows the addressable audience to one corner of the web ecosystem and risks framework-specific shortcuts leaking into the core.
- **Pure framework-agnostic with no framework heuristics.** Rejected — would leave diff-aware test selection useless for the most common framework families and remove a real productivity win.

## References

- our product spec Open Question #8 + recommended answer
- the documentation Discovery
- the documentation CI modes (diff-aware selection)
- Related ADRs: ADR-0010 (Discovery MVP), ADR-0022 (CI integration), ADR-0031 (Example apps)
