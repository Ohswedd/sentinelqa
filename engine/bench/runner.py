# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Bench runner — measure the four SLO metrics."""

from __future__ import annotations

import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import closing
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from engine.bench.report import BenchMetric, BenchReport

_BENCH_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "scripts" / "_audit_of_self_fixture"


def _resolve_sentinelqa_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("sentinelqa-cli")
    except (PackageNotFoundError, ImportError):
        return "0.0.0"


def _measure_seconds(samples: int, fn: callable[[], None]) -> float:  # type: ignore[valid-type]
    """Run ``fn`` ``samples`` times and return the median wall-clock seconds.

    Median is the right summary here: cold-start has long-tailed outliers
    (GC pauses, fs cache misses) we don't want to count toward the SLO.
    """

    timings: list[float] = []
    for _ in range(samples):
        start = time.perf_counter()
        fn()
        timings.append(time.perf_counter() - start)
    return statistics.median(timings)


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _serve(directory: Path, port: int) -> HTTPServer:
    handler = type("Handler", (_QuietHandler,), {"directory": str(directory)})
    server = HTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for _ in range(50):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.02)
    return server


def _bench_import_time(samples: int) -> BenchMetric:
    """``python -c "import sentinel_cli"`` cold-start."""

    cmd = [sys.executable, "-c", "import sentinel_cli  # noqa: F401"]

    def _once() -> None:
        subprocess.run(cmd, check=True, capture_output=True)

    return BenchMetric(
        name="import_time_s",
        value_seconds=_measure_seconds(samples, _once),
        samples=samples,
    )


def _bench_cli_cold_start(samples: int) -> BenchMetric:
    """``sentinel --version`` spawn → exit."""

    cmd = ["uv", "run", "sentinel", "--version"]

    def _once() -> None:
        subprocess.run(cmd, check=True, capture_output=True)

    return BenchMetric(
        name="cli_cold_start_s",
        value_seconds=_measure_seconds(samples, _once),
        samples=samples,
    )


def _write_bench_config(workspace: Path, port: int) -> Path:
    config_path = workspace / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: bench\n"
        "  framework: nextjs\n"
        "  package_manager: pnpm\n"
        f"target:\n"
        f"  base_url: http://127.0.0.1:{port}\n"
        "  allowed_hosts:\n"
        "    - 127.0.0.1\n"
        "modules:\n"
        "  functional: false\n"
        "  api: false\n"
        "  accessibility: false\n"
        "  performance: false\n"
        "  visual: false\n"
        "  security: false\n"
        "  llm_audit: false\n"
        "discovery:\n"
        '  engine: "http"\n'
        "  max_depth: 2\n"
        "  max_pages: 8\n"
        "  rate_limit_rps: 50.0\n"
        "  respect_robots: false\n"
        "  same_host_only: true\n",
        encoding="utf-8",
    )
    return config_path


def _bench_full_audit(samples: int) -> tuple[BenchMetric, BenchMetric]:
    """Run ``sentinel discover`` against the audit-of-self fixture.

    Returns two metrics: the full wall-clock (``full_audit_s``) and
    ``time_to_first_finding_s`` — for the discovery flow this is the
    moment the run directory appears on disk (downstream a real audit
    would wire this to the first finding emission, but the hermetic
    fixture has no findings; we use the run-dir appearance as the
    structural equivalent: the discover loop reached the persist step).
    """

    fixture_dir = _BENCH_FIXTURE_DIR
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "index.html").write_text(
        "<!doctype html><html><body><a href=/about.html>a</a></body></html>",
        encoding="utf-8",
    )
    (fixture_dir / "about.html").write_text(
        "<!doctype html><html><body>about</body></html>",
        encoding="utf-8",
    )

    full_timings: list[float] = []
    ttff_timings: list[float] = []

    for _ in range(samples):
        port = _free_port()
        server = _serve(fixture_dir, port)
        try:
            with tempfile.TemporaryDirectory(prefix="sentinelqa-bench-") as workdir:
                workspace = Path(workdir)
                config_path = _write_bench_config(workspace, port)
                runs_dir = workspace / ".sentinel" / "runs"
                runs_dir.mkdir(parents=True, exist_ok=True)

                cmd = [
                    "uv",
                    "run",
                    "sentinel",
                    "--config",
                    str(config_path),
                    "discover",
                    "--url",
                    f"http://127.0.0.1:{port}",
                    "--output",
                    str(runs_dir),
                ]
                start = time.perf_counter()
                completed = subprocess.run(cmd, capture_output=True, check=True)
                full_elapsed = time.perf_counter() - start

                # Pick the per-run directory created by the discover loop.
                run_dirs = [p for p in runs_dir.iterdir() if p.name.startswith("RUN-")]
                if not run_dirs:
                    raise RuntimeError(
                        "sentinel discover did not produce a RUN- directory; "
                        f"stderr was: {completed.stderr!r}"
                    )
                run_dir = run_dirs[0]
                # Use the mtime of the FIRST persisted artefact as the
                # structural equivalent of "first finding" — it's the
                # moment the discover loop committed observable state.
                first_mtime = min(p.stat().st_mtime for p in run_dir.iterdir())
                ttff = max(0.0, first_mtime - (time.perf_counter() - full_elapsed))
                if ttff <= 0.0 or ttff > full_elapsed:
                    ttff = full_elapsed
                full_timings.append(full_elapsed)
                ttff_timings.append(min(ttff, full_elapsed))
        finally:
            server.shutdown()
            server.server_close()

    return (
        BenchMetric(
            name="time_to_first_finding_s",
            value_seconds=statistics.median(ttff_timings),
            samples=samples,
        ),
        BenchMetric(
            name="full_audit_s",
            value_seconds=statistics.median(full_timings),
            samples=samples,
        ),
    )


def run_bench(
    *,
    import_samples: int = 3,
    cli_samples: int = 3,
    audit_samples: int = 2,
) -> BenchReport:
    """Measure every SLO metric and return a :class:`BenchReport`.

    Samples are small by default so the bench fits inside a CI minute.
    Pass larger ``audit_samples`` (e.g. 5) on the workstation to dampen
    cold-cache jitter.
    """

    metrics: list[BenchMetric] = []
    metrics.append(_bench_import_time(import_samples))
    metrics.append(_bench_cli_cold_start(cli_samples))
    ttff, full = _bench_full_audit(audit_samples)
    metrics.append(ttff)
    metrics.append(full)
    return BenchReport(
        sentinelqa_version=_resolve_sentinelqa_version(),
        metrics=tuple(metrics),
    )


__all__ = ["run_bench"]
