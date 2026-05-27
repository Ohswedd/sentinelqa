# Task 17.02 — GitLab CI template

## Deliverables

- `integrations/gitlab/.gitlab-ci.sentinel.yml` — drop-in include that:
  - Caches pip + node_modules.
  - Runs `sentinel ci` with the same modes.
  - Uploads artifacts.
  - Publishes JUnit + SARIF + Markdown to merge request notes via the GitLab API (using a project access token).
- Documented at `integrations/gitlab/README.md` with copy-paste include snippet.

## Acceptance criteria

- The template runs successfully against the fixture in a smoke pipeline.

## Tests required

- Manual GitLab smoke once (CI-only verification noted in PR).

## PRD / CLAUDE.md references

- PRD §21.
- CLAUDE.md §39.

## Definition of Done

- [ ] Template authored.
- [ ] Smoke pipeline green.
- [ ] `STATUS.md` updated.
