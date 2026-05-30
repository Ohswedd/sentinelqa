"""Phase 29.04 — `make bench` driver.

Measures the four wall-clock targets in
``plans/phase-29-final-hardening/04-performance-audit.md``:

1. ``python -c "import sentinel_cli"`` (cold import, target < 200 ms).
2. ``sentinel --version`` (cold start, target < 300 ms).
3. ``sentinel doctor --json`` against a healthy local config (target < 3 s).
4. (Optional) ``sentinel audit`` against a running example (target < 10 min).
   The audit run is gated behind ``--audit-url`` so this script is fast by
   default — the live Next.js boot is not always available in CI.

Each measurement is repeated ``--repeat`` times (default 3) and the median
is reported alongside the min/max. Memory peak is captured via
``resource.getrusage`` of the child process.

Output: human-readable table to stdout, plus an optional JSON dump under
``--output <path>``.
"""

from __future__ import annotations

import argparse
import json
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIN_CONFIG = REPO_ROOT / "scripts" / "_bench_minimal_config.yaml"

DEFAULT_CONFIG_BODY: str = """\
version: 1
project:
  name: bench
  framework: nextjs
  package_manager: pnpm
source:
  root: .
target:
  base_url: http://127.0.0.1:65535
  allowed_hosts:
    - 127.0.0.1
"""

BENCH_TARGETS_MS: dict[str, float] = {
    "import_sentinel_cli": 200.0,
    "sentinel_version": 300.0,
    "sentinel_doctor": 3000.0,
    "sentinel_audit": 10 * 60 * 1000.0,
}


def _ensure_config() -> Path:
    if not MIN_CONFIG.exists():
        MIN_CONFIG.write_text(DEFAULT_CONFIG_BODY, encoding="utf-8")
    return MIN_CONFIG


def _run_once(cmd: list[str]) -> tuple[float, int]:
    """Return (wall_ms, max_rss_kb) for one execution of ``cmd``."""

    rusage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.perf_counter()
    completed = subprocess.run(cmd, capture_output=True)
    t1 = time.perf_counter()
    rusage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    if completed.returncode != 0:
        sys.stderr.write(
            f"\n[bench] command exited {completed.returncode}: {' '.join(cmd)}\n"
            f"stdout: {completed.stdout.decode(errors='ignore')[:500]}\n"
            f"stderr: {completed.stderr.decode(errors='ignore')[:500]}\n"
        )
    # max_rss delta avoids double-counting prior children.
    rss_delta = max(0, rusage_after.ru_maxrss - rusage_before.ru_maxrss)
    return (t1 - t0) * 1000.0, rss_delta


def _summarize(label: str, samples: list[tuple[float, int]]) -> dict[str, float | str]:
    walls = [w for w, _ in samples]
    rss = [r for _, r in samples]
    return {
        "label": label,
        "samples": len(walls),
        "median_ms": statistics.median(walls),
        "min_ms": min(walls),
        "max_ms": max(walls),
        "max_rss_kb": max(rss),
        "target_ms": BENCH_TARGETS_MS.get(label, float("nan")),
        "verdict": (
            "under-budget"
            if statistics.median(walls) <= BENCH_TARGETS_MS.get(label, float("inf"))
            else "OVER-BUDGET"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench", description=__doc__)
    parser.add_argument("--repeat", type=int, default=3, help="Repeats per case (default 3).")
    parser.add_argument(
        "--audit-url",
        default=None,
        help="If supplied, also measure `sentinel audit --url <URL>`.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write a JSON report.",
    )
    args = parser.parse_args(argv)

    config = _ensure_config()
    repeats = max(1, args.repeat)

    cases: list[tuple[str, list[str]]] = [
        (
            "import_sentinel_cli",
            ["uv", "run", "python", "-c", "import sentinel_cli"],
        ),
        ("sentinel_version", ["uv", "run", "sentinel", "--version"]),
        (
            "sentinel_doctor",
            [
                "uv",
                "run",
                "sentinel",
                "--config",
                str(config),
                "--ci",
                "--json",
                "doctor",
            ],
        ),
    ]
    if args.audit_url:
        cases.append(
            (
                "sentinel_audit",
                [
                    "uv",
                    "run",
                    "sentinel",
                    "--config",
                    str(config),
                    "audit",
                    "--url",
                    args.audit_url,
                ],
            )
        )

    summary: list[dict[str, float | str]] = []
    for label, cmd in cases:
        samples = [_run_once(cmd) for _ in range(repeats)]
        summary.append(_summarize(label, samples))

    width = max(len(row["label"]) for row in summary) if summary else 10  # type: ignore[arg-type]
    print(f"{'case':<{width}}  median_ms  min_ms  max_ms  target_ms  verdict")
    for row in summary:
        print(
            f"{row['label']:<{width}}  "
            f"{row['median_ms']:>9.1f}  "
            f"{row['min_ms']:>6.1f}  "
            f"{row['max_ms']:>6.1f}  "
            f"{row['target_ms']:>9.1f}  "
            f"{row['verdict']}"
        )

    if args.output:
        args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.output}")

    return 0 if all(row["verdict"] == "under-budget" for row in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
