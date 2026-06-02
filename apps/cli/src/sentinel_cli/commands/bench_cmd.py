"""``sentinel bench`` CLI command (v1.8.0, phase 38).

Runs the SLO suite (import time, CLI cold-start, time-to-first-finding,
full-audit wall-clock) and optionally diffs the result against a
baseline file. Exits non-zero when any metric regresses beyond the
threshold ratio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from engine.bench import (
    DEFAULT_REGRESSION_THRESHOLD,
    compare_to_baseline,
    load_report,
    run_bench,
    write_report,
)


def run_bench_command(
    ctx: typer.Context,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write the measured BenchReport JSON here (default: stdout-only).",
        ),
    ] = None,
    compare_to: Annotated[
        Path | None,
        typer.Option(
            "--compare-to",
            help=(
                "Baseline BenchReport JSON. Exits non-zero on regression "
                "beyond --threshold (default 10%)."
            ),
        ),
    ] = None,
    threshold: Annotated[
        float,
        typer.Option(
            "--threshold",
            help=(
                "Per-metric regression threshold as a ratio. 0.10 means "
                "fail if any metric is >10% slower than baseline."
            ),
        ),
    ] = DEFAULT_REGRESSION_THRESHOLD,
    import_samples: Annotated[
        int,
        typer.Option("--import-samples", help="Samples for the import-time metric."),
    ] = 3,
    cli_samples: Annotated[
        int,
        typer.Option("--cli-samples", help="Samples for the CLI cold-start metric."),
    ] = 3,
    audit_samples: Annotated[
        int,
        typer.Option("--audit-samples", help="Samples for the full-audit metric."),
    ] = 2,
) -> None:
    """Measure the SLO suite and optionally gate on baseline regression."""

    del ctx  # bench is config-less; runs against a hermetic fixture.

    typer.echo("Running SLO benchmark suite (median over samples)...")
    report = run_bench(
        import_samples=import_samples,
        cli_samples=cli_samples,
        audit_samples=audit_samples,
    )

    for metric in report.metrics:
        typer.echo(
            f"  {metric.name:30s} {metric.value_seconds:8.3f}s   " f"(samples={metric.samples})"
        )

    if output is not None:
        write_report(output, report)
        typer.echo(f"Wrote: {output}")

    if compare_to is None:
        return

    baseline = load_report(compare_to)
    comparison = compare_to_baseline(
        report,
        baseline,
        default_threshold=threshold,
    )
    typer.echo("")
    typer.echo(comparison.render_text())
    if comparison.has_regressions:
        raise typer.Exit(code=1)
