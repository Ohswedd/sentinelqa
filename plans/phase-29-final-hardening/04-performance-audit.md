# Task 29.04 — Self-performance audit

## Deliverables

- Measure and document on a reference machine:
  - `python -c "import sentinelqa"` import time (target < 200 ms).
  - `sentinel --version` (target < 300 ms).
  - `sentinel doctor` wall-clock on a healthy machine (target < 3 s end-to-end).
  - Full `sentinel audit --url http://localhost:3000` on the Next.js example (target < 10 min).
  - Memory peak (target < 1 GB).
- Add `make bench` running these and emitting a report.

## Sub-checks the audit must answer

- **Reachability probe in `sentinel doctor`** (Phase 02 carry-over): the probe currently uses a synchronous `httpx.head(url, timeout=5.0)` call inside `apps/cli/src/sentinel_cli/commands/doctor_cmd.py::_check_reachability`. If `sentinel doctor` lands above the 3 s budget on a healthy machine, OR if a future phase adds additional network probes that would benefit from concurrency, convert that single call site to async (`httpx.AsyncClient.head`) and gather every network-bound check (`reachability`, plus anything Phase 17 / Phase 25 adds). Until the bench shows a bottleneck, leave the synchronous form — the simplicity is worth the latency.
- Cold-start vs warm-start delta: report both. If cold-start dominates, profile import time before optimizing runtime calls.

## Acceptance criteria

- Targets met (or noted with justification + tracked issue).
- The reachability-probe sub-check above has an explicit verdict (kept synchronous, or converted with measurement before/after).

## Definition of Done

- [ ] Bench results committed in `docs/release/perf-audit-<date>.md`.
- [ ] Reachability-probe verdict recorded in the same doc.
- [ ] `STATUS.md` updated.
