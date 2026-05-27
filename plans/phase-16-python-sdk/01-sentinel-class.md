# Task 16.01 — `Sentinel` facade

## Deliverables

- `packages/python-sdk/sentinelqa/__init__.py` exporting `Sentinel`, `AuditResult`, `Finding`, `Evidence`, `TestPlan`, `Flow`, `RiskMap`, `QualityGate`, `Policy`, `ModuleResult`, `RepairSuggestion`.
- `Sentinel` class:
  - Constructor: `Sentinel(project_path=".", *, config: str|Path|None=None, machine_readable: bool=False)`.
  - Class method: `Sentinel.from_config(path) -> Sentinel`.
  - Methods (sync): `discover(url) -> DiscoveryGraph`, `plan(url|graph) -> TestPlan`, `generate_tests(plan, out_dir) -> None`, `audit(url, *, modules=None, safe_mode=True) -> AuditResult`, `report(run_id|latest) -> Path`, `verify_fix(run_id, suggestion) -> AuditResult`.
  - Methods (async): `Sentinel.async_audit(...)`, `Sentinel.async_discover(...)` etc.
- Every method calls the orchestrator from Phase 02; the SDK is **only** a thin facade.

## Acceptance criteria

- PRD §14.1 example works exactly as written.
- PRD §14.2 agent-friendly example works.

## Tests required

- `tests/unit/sdk/test_sentinel_facade.py`.
- `tests/integration/sdk/test_audit_against_fixture.py`.

## PRD / CLAUDE.md references

- PRD §14.
- CLAUDE.md §14.

## Definition of Done

- [ ] Facade implemented; both PRD examples reproduce.
- [ ] `STATUS.md` updated.
