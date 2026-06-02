# SLO baselines

`baseline.json` pins the v1.8.0 cold-start + audit wall-clock SLOs for
the CI `bench-slo` gate. The file is read by the `sentinel bench
--compare-to slo/baseline.json` command (engine/bench/compare.py).

## Metrics

| Metric                    | What it measures                                            |
| ------------------------- | ----------------------------------------------------------- |
| `import_time_s`           | `python -c "import sentinel_cli"` cold-start.               |
| `cli_cold_start_s`        | `sentinel --version` spawn → exit.                          |
| `time_to_first_finding_s` | `sentinel discover` until first artefact persists.          |
| `full_audit_s`            | Full `sentinel discover` against the audit-of-self fixture. |

Each value is the median over `samples` independent measurements;
median is the right summary because cold-start has long-tailed
outliers (GC, fs cache misses) we don't want to count toward the SLO.

## Updating the baseline

A baseline change is a release-engineering decision, not a routine
PR. Update only when:

1. **A real perf improvement landed.** Cut the baseline to lock the
   improvement in. Future regressions then trip the gate sooner.
2. **A justified slowdown landed** (new feature, sound architectural
   choice). Bump the baseline and reference the PR / ADR in the
   commit message.

The CI gate fails when any measured metric exceeds its baseline value
by more than 10 % (configurable per-metric in
`engine/bench/compare.py:DEFAULT_REGRESSION_THRESHOLD`). The current
baseline values include headroom for GitHub-hosted runner jitter.

### Historical baseline

| Version | import_time | cli_cold_start | ttff   | full_audit | Notes                                                                |
| ------- | ----------- | -------------- | ------ | ---------- | -------------------------------------------------------------------- |
| 1.8.0   | 1.5 s       | 1.5 s          | 3.0 s  | 3.0 s      | Initial — generous so the first CI run wouldn't trip the gate.       |
| 1.8.0   | 1.5 s       | 1.5 s          | 2.0 s  | 2.0 s      | Tightened mid-release after the first green CI run.                  |
| 1.10.0  | 1.4 s       | 1.4 s          | 1.85 s | 1.85 s     | Ratcheted down from observed v1.9.0 CI medians (1.17 / 1.22 / 1.60). |

## Local development

Run the suite locally to compare your branch against `main`:

```bash
uv run sentinel bench --output /tmp/local.json
uv run sentinel bench --compare-to slo/baseline.json
```

Use larger sample counts (`--audit-samples 5`) on the workstation to
dampen cold-cache jitter; CI uses smaller counts to fit inside a
minute.
