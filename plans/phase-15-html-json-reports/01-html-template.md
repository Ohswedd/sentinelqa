# Task 15.01 — HTML template

## Deliverables

- `engine/reporter/html/` containing:
  - `template.html.j2` — server-rendered Jinja2 template; no JS frameworks required.
  - `styles.css` (minimal, ≤ 30 KB, no Tailwind/Bootstrap).
  - `app.js` (≤ 30 KB) for filter/sort interactions; vanilla.
  - All assets bundled into the final `report.html` via inline `<style>` and `<script>` tags so the report is one self-contained file.
- Template sections (CLAUDE §38 / PRD §38 questions):
  - Header: score badge, decision badge, run id, target, duration.
  - Summary panel.
  - Per-module section with findings table and counts.
  - Critical-blocker section pinned at top.
  - Evidence drawer (lazy-loads images / videos from the run dir using relative paths).
  - Footer with config snapshot hash, schema versions, links to JSON/SARIF/JUnit, link to docs.
- Theme: light + dark via `prefers-color-scheme`.

## Steps

1. Build the template.
2. Inline assets at write time.
3. Make sure every link uses a relative path so the report works wherever it's moved.

## Acceptance criteria

- `report.html` is self-contained; opens correctly from `file://`.
- No CDN calls; HTML's `<link>` and `<script>` tags only reference inline content or relative paths within the run dir.

## Tests required

- `tests/integration/reporter/test_html_self_contained.py` (verifies no external URLs via regex + offline render).
- `tests/golden/reports/test_html_template.py`.

## PRD / CLAUDE.md references

- PRD §9.7, §20, §38.
- CLAUDE.md §38, §41 (no telemetry/CDN).

## Definition of Done

- [ ] Self-contained HTML report renders.
- [ ] No external URLs.
- [ ] Golden test stable.
- [ ] `STATUS.md` updated.
