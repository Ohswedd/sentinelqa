# Task 28.03 — Package metadata

## Deliverables

- `apps/cli/pyproject.toml` + `packages/python-sdk/pyproject.toml`: name, version, description, license (Apache-2.0), authors, urls (homepage, docs, source, issues, changelog), classifiers, keywords, readme, python-requires.
- `packages/ts-runtime/package.json` + others: name, version, description, license, repository, author, keywords, files.
- Generated `*.dist-info/METADATA` and npm package metadata audited.

## Acceptance criteria

- Metadata audit script: `make audit-metadata` passes (verifies required fields present, no AI authors).

## Tests required

- `tests/integration/release/test_metadata.py`.

## Definition of Done

- [ ] Metadata complete + audited.
- [ ] `STATUS.md` updated.
