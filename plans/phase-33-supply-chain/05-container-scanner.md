# Task 33.05 — Container image scanner adapter

## Deliverables

- `modules/supply_chain/container.py`. If
  `policy.supply_chain.container_image` is set:
  - Shell out to `trivy image --format json` if available; else to
    `grype <image> -o json`. Detection cached for the session.
  - If neither is installed, finding `container-scanner-not-installed`
    with `severity: info` and a recommendation to install one.
    Module status `skipped`.
  - Normalise Trivy / Grype JSON into the SentinelQA finding shape;
    every CVE gets a finding with `cwe_id` derived from the advisory.
- The scanner runs only against the configured image; it does NOT
  pull, does NOT scan random images, does NOT iterate over a registry.
- Configurable cap `policy.supply_chain.container.max_findings`
  (default 200) so a CVE-heavy image doesn't flood the report.

## Tests required

- `tests/unit/modules/supply_chain/test_container_trivy_parser.py`
  — fixture of real Trivy JSON; SentinelQA findings emitted.
- `tests/unit/modules/supply_chain/test_container_grype_parser.py`
  — same for Grype.
- `tests/unit/modules/supply_chain/test_container_no_binary.py` —
  graceful `skipped` path.

## Definition of Done

- [ ] Two binary adapters, one normalised output shape.
- [ ] Cap enforced.
- [ ] `STATUS.md` updated.
