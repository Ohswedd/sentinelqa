"""Container scanner — graceful skipped paths (Phase 33.05)."""

from __future__ import annotations

import subprocess

from modules.supply_chain.container import scan_container, select_scanner


def test_no_image_skips_cleanly() -> None:
    report = scan_container(image=None)
    assert report.skipped is True
    assert report.scanner == "none"
    assert "image is not set" in (report.skipped_reason or "")


def test_no_binary_skips_with_info_recommendation() -> None:
    def fake_which(_name: str) -> str | None:
        return None

    report = scan_container(image="example:tag", which=fake_which)
    assert report.skipped is True
    assert report.scanner == "none"
    assert report.skipped_reason and "container-scanner-not-installed" in report.skipped_reason


def test_select_scanner_prefers_trivy() -> None:
    def which_trivy(name: str) -> str | None:
        return "/usr/bin/trivy" if name == "trivy" else None

    def which_grype(name: str) -> str | None:
        return "/usr/bin/grype" if name == "grype" else None

    def which_both(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in {"trivy", "grype"} else None

    assert select_scanner(which=which_trivy) == "trivy"
    assert select_scanner(which=which_grype) == "grype"
    assert select_scanner(which=which_both) == "trivy"
    assert select_scanner(which=lambda _name: None) == "none"


def test_unparseable_json_is_skipped() -> None:
    def fake_run(_argv):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="not json", stderr="")

    report = scan_container(
        image="example:tag",
        scanner="trivy",
        run_callable=fake_run,
    )
    assert report.skipped is True
    assert "unparseable JSON" in (report.skipped_reason or "")


def test_subprocess_error_is_skipped() -> None:
    def fake_run(_argv):  # type: ignore[no-untyped-def]
        raise FileNotFoundError("missing binary")

    report = scan_container(
        image="example:tag",
        scanner="trivy",
        run_callable=fake_run,
    )
    assert report.skipped is True
    assert "trivy invocation failed" in (report.skipped_reason or "")
