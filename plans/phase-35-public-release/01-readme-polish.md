# Task 35.01 — Public-facing README polish

## Deliverables

- Rewrite `README.md` for public consumption. Required sections:
  1. **Badges** — CI status, codecov, PyPI version, npm version,
     Docker pulls, License, Python versions, Node version,
     "v0.7.0" tag once minted.
  2. **One-paragraph pitch** — what SentinelQA is, who it's for, why
     it exists (release-confidence for LLM-built apps). Reuse the
     Phase 27 positioning doc; no marketing fluff.
  3. **Quickstart** — three commands:
     ```bash
     uv pip install sentinelqa-cli
     sentinel init
     sentinel audit --url http://localhost:3000
     ```
  4. **What it does today** — bullet list mapping the public modules
     (discovery / planner / generator / runner / analyzer +
     functional / a11y / perf / security / api / visual / chaos /
     llm-audit) to one-line summaries.
  5. **Demo asset** — animated GIF or terminal SVG (`docs/assets/`)
     of an actual run. No fake screenshots.
  6. **Docs site link** — the Cloudflare Pages URL from task 35.04.
  7. **Contributing** — pointer to `CONTRIBUTING.md`; "we accept PRs
     against `main` via the standard fork-and-PR flow".
  8. **Safety & legal** — the CLAUDE.md §6 boundary in plain English:
     "SentinelQA is for authorized testing only". Link to
     `SECURITY.md`.
  9. **License** — Apache-2.0; link to `LICENSE`.
- Badges use `shields.io` (preferred) with absolute URLs to the
  GitHub repo + the PyPI / npm package names.
- README is checked into the repo. Public site uses the same content
  via the Phase 27 docs site's landing page; no drift.

## Tests required

- `tests/integration/docs/test_readme_links.py` — every URL in
  README is well-formed; relative paths resolve in-repo.

## Definition of Done

- [ ] README < 250 lines.
- [ ] No "AI-powered" / "magic" / "intelligent" buzzwords.
- [ ] Every claim in README has a doc page that proves it.
- [ ] `STATUS.md` updated.
