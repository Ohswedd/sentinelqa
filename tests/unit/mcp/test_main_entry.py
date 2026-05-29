"""Coverage for ``python -m sentinelqa_mcp`` entry point."""

from __future__ import annotations

from pathlib import Path

from sentinelqa_mcp.__main__ import main


def _write_minimal_config(root: Path) -> Path:
    cfg = root / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\n"
        "project:\n  name: p\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts:\n    - localhost\n"
        "modules:\n  functional: true\n  api: false\n  accessibility: false\n"
        "  performance: false\n  visual: false\n  security: false\n"
        "  chaos: false\n  llm_audit: false\n",
        encoding="utf-8",
    )
    return cfg


def test_main_http_zero_refused(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_minimal_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = main(["--http", "0", "--config", str(cfg)])
    # Port 0 is out of LoopbackHttpTransport's [1, 65535] window.
    assert rc == 4


def test_main_http_out_of_range_refused(tmp_path: Path, monkeypatch) -> None:
    cfg = _write_minimal_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = main(["--http", "70000", "--config", str(cfg)])
    assert rc == 4


def test_main_config_missing_does_not_crash(tmp_path: Path, monkeypatch) -> None:
    """When the config doesn't exist, build_default_server falls back to
    the SDK's default state. The actual config error surfaces only when
    a tool runs, so a missing config here just hits the transport
    validation path (exit 4 for the bad --http value)."""

    monkeypatch.chdir(tmp_path)
    missing = tmp_path / "absent.yaml"
    rc = main(["--http", "70000", "--config", str(missing)])
    assert rc == 4


def test_main_help_via_argparse(capsys, monkeypatch) -> None:
    # SystemExit is raised by argparse on --help; we catch and inspect.
    import pytest

    monkeypatch.chdir(Path.cwd())
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "sentinelqa-mcp" in captured.out
    assert "--stdio" in captured.out
