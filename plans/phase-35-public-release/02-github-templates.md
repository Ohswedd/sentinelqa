# Task 35.02 — GitHub community files

## Deliverables

- `.github/ISSUE_TEMPLATE/bug_report.yml` (issue forms, structured).
- `.github/ISSUE_TEMPLATE/feature_request.yml`.
- `.github/ISSUE_TEMPLATE/security_disclosure.yml` (links to the
  private disclosure path in `SECURITY.md`; the form itself is just
  the link).
- `.github/PULL_REQUEST_TEMPLATE.md` — checklist (tests, docs, ADR if
  needed, no AI co-author trailer, Conventional Commit).
- `.github/CODE_OF_CONDUCT.md` — Contributor Covenant 2.1, English,
  contact `security@sentinelqa.dev` (placeholder; owner updates).
- `SECURITY.md` — private disclosure path; PGP key fingerprint
  placeholder; supported-versions matrix tied to the v0.7.0 + v1.0.0
  tags in `docs/dev/semver.md`.
- `CONTRIBUTING.md` polish — branching model (already in
  `CLAUDE.md` §4), commit conventions, where to file bugs vs
  questions, the per-phase loop pointer for big features.

## Tests required

- `tests/integration/docs/test_community_files.py` — every required
  file present; well-formed YAML in issue forms.

## Definition of Done

- [ ] GitHub "Community Standards" badge would read 100 % once the
      repo is public (verified locally via gh-community-checker or
      by inspection).
- [ ] No placeholder email leaks into a tracked commit unless wrapped
      in `<placeholder>` markers.
- [ ] `STATUS.md` updated.
