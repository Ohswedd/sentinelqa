"""End-to-end build + install smoke test.

This test:

1. Builds every Python sdist + wheel (``uv build --all-packages``) and the TS
 tarball (``pnpm pack``) into a temp dir.
2. Inspects every artifact for forbidden contents (.git,.env, secrets,
 __pycache__, …).
3. Installs the four published Python wheels into a fresh venv via
 ``uv pip install`` and runs ``sentinel --version`` to prove the sdist /
 wheel layout actually lands a working CLI.

The full cycle takes ~30s, so the slow marker keeps it out of the default
``make ci`` test sweep. ``make test-full`` runs it; the gate review
runs it explicitly.

Lighter, faster tests (the inspector unit-tests + a synthetic-tarball fixture)
cover the inspector's logic without paying the build cost.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _ensure_scripts_on_path() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _path() -> None:
    _ensure_scripts_on_path()


# --------------------------------------------------------------------------- #
# Inspector unit tests — no subprocess; synthetic in-memory archives.
# --------------------------------------------------------------------------- #


def _write_tarball(path: Path, files: dict[str, bytes]) -> None:
    with tarfile.open(path, mode="w:gz") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


def _write_wheel(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, mode="w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)


def test_inspector_passes_on_clean_wheel(tmp_path: Path) -> None:
    from scripts.release.inspect_built_packages import inspect_artifact

    wheel = tmp_path / "clean-0.1.0-py3-none-any.whl"
    _write_wheel(
        wheel,
        {
            "engine/__init__.py": b"# clean\n",
            "engine/domain/foo.py": b"\n",
        },
    )
    assert inspect_artifact(wheel) == []


def test_inspector_flags_dotenv(tmp_path: Path) -> None:
    from scripts.release.inspect_built_packages import inspect_artifact

    wheel = tmp_path / "leak-0.1.0-py3-none-any.whl"
    _write_wheel(wheel, {"package/.env": b"SECRET=1\n", "package/__init__.py": b"\n"})
    hits = inspect_artifact(wheel)
    assert any(reason == "dotenv_file" for reason, _ in hits)


def test_inspector_flags_pem(tmp_path: Path) -> None:
    from scripts.release.inspect_built_packages import inspect_artifact

    tar = tmp_path / "leak.tar.gz"
    _write_tarball(
        tar,
        {
            "pkg/private.pem": b"-----BEGIN PRIVATE KEY-----\n",
            "pkg/__init__.py": b"\n",
        },
    )
    hits = inspect_artifact(tar)
    assert any(reason == "private_key_pem" for reason, _ in hits)


def test_inspector_flags_pycache(tmp_path: Path) -> None:
    from scripts.release.inspect_built_packages import inspect_artifact

    wheel = tmp_path / "wheel.whl"
    _write_wheel(
        wheel,
        {
            "engine/__pycache__/foo.cpython-312.pyc": b"\n",
            "engine/__init__.py": b"\n",
        },
    )
    hits = inspect_artifact(wheel)
    reasons = {r for r, _ in hits}
    assert "py_cache_dir" in reasons or "py_cache_pyc" in reasons


def test_inspector_flags_git_directory(tmp_path: Path) -> None:
    from scripts.release.inspect_built_packages import inspect_artifact

    tar = tmp_path / "with-git.tar.gz"
    _write_tarball(
        tar,
        {
            "pkg/.git/HEAD": b"ref: refs/heads/main\n",
            "pkg/__init__.py": b"\n",
        },
    )
    hits = inspect_artifact(tar)
    assert any(reason == "git_directory" for reason, _ in hits)


def test_inspector_flags_cloud_credentials(tmp_path: Path) -> None:
    from scripts.release.inspect_built_packages import inspect_artifact

    tar = tmp_path / "leak.tar.gz"
    _write_tarball(
        tar,
        {
            "pkg/service-account-prod.json": b"{}",
            "pkg/__init__.py": b"\n",
        },
    )
    hits = inspect_artifact(tar)
    assert any(reason == "cloud_creds" for reason, _ in hits)


def test_inspect_all_aggregates_per_artifact(tmp_path: Path) -> None:
    from scripts.release.inspect_built_packages import inspect_all

    dist = tmp_path / "dist"
    dist.mkdir()
    _write_wheel(dist / "clean.whl", {"a/__init__.py": b"\n"})
    _write_wheel(dist / "leak.whl", {"a/.env": b"\n", "a/__init__.py": b"\n"})
    failures = inspect_all(dist)
    assert (dist / "leak.whl") in failures
    assert (dist / "clean.whl") not in failures


# --------------------------------------------------------------------------- #
# Build artifact catalogue helpers
# --------------------------------------------------------------------------- #


def test_build_artifacts_dataclass_round_trip(tmp_path: Path) -> None:
    from scripts.release.build_all import BuildArtifacts

    wheel = tmp_path / "x.whl"
    wheel.write_bytes(b"")
    sdist = tmp_path / "x.tar.gz"
    sdist.write_bytes(b"")
    art = BuildArtifacts(out_dir=tmp_path, python_wheels=[wheel], python_sdists=[sdist])
    assert sorted(p.name for p in art.all_files()) == ["x.tar.gz", "x.whl"]


# --------------------------------------------------------------------------- #
# Full build + install smoke test (slow tier).
# --------------------------------------------------------------------------- #


def _have_pnpm() -> bool:
    return shutil.which("pnpm") is not None


def _have_uv() -> bool:
    return shutil.which("uv") is not None


@pytest.mark.slow
@pytest.mark.skipif(not _have_uv(), reason="uv not on PATH")
@pytest.mark.skipif(not _have_pnpm(), reason="pnpm not on PATH")
def test_build_inspect_install_and_run_sentinel_version(tmp_path: Path) -> None:
    from scripts.release.build_all import build_all
    from scripts.release.inspect_built_packages import inspect_all

    out_dir = tmp_path / "dist"
    artifacts = build_all(out_dir, build_docker=False)

    # Expect 6 Python wheels (sentinelqa-engine, sentinelqa-modules,
    # sentinelqa-integrations, sentinelqa, sentinelqa-mcp, sentinelqa-cli),
    # 6 matching sdists, and 1 TS tarball.
    assert len(artifacts.python_wheels) == 6, [p.name for p in artifacts.python_wheels]
    assert len(artifacts.python_sdists) == 6, [p.name for p in artifacts.python_sdists]
    assert len(artifacts.ts_tarballs) == 1, [p.name for p in artifacts.ts_tarballs]

    # No forbidden contents in any built artifact.
    findings = inspect_all(out_dir)
    assert findings == {}, f"forbidden files in artifacts: {findings}"

    # Wheels must include their METADATA file with the Apache-2.0 trove
    # classifier (proves 's polish actually reached the wheel).
    for wheel in artifacts.python_wheels:
        with zipfile.ZipFile(wheel) as zf:
            metadata_paths = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
            assert metadata_paths, f"{wheel.name} missing METADATA"
            text = zf.read(metadata_paths[0]).decode("utf-8")
            assert "Apache Software License" in text, f"{wheel.name} missing Apache classifier"

    # Spin up a venv, install the four wheels, run `sentinel --version`.
    venv_dir = tmp_path / ".venv-test"
    subprocess.run(
        ["uv", "venv", str(venv_dir), "--python", "3.12"],
        capture_output=True,
        text=True,
        check=True,
    )
    # Install order: engine → modules + integrations → sdk + mcp → cli.
    # `uv pip install --python <venv-python>` installs into the target venv.
    venv_python = venv_dir / "bin" / "python"
    install_targets = (
        sorted(out_dir.glob("sentinelqa_engine-*.whl"))
        + sorted(out_dir.glob("sentinelqa_modules-*.whl"))
        + sorted(out_dir.glob("sentinelqa_integrations-*.whl"))
        + sorted(out_dir.glob("sentinelqa-*.whl"))
        + sorted(out_dir.glob("sentinelqa_mcp-*.whl"))
        + sorted(out_dir.glob("sentinelqa_cli-*.whl"))
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(venv_python),
            *[str(p) for p in install_targets],
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    # Run `sentinel --version` from the venv.
    result = subprocess.run(
        [str(venv_dir / "bin" / "sentinel"), "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    combined = (result.stdout + result.stderr).lower()
    # Accept either "sentinel" branding or a semver-looking string — the
    # version line evolves but at least one is always present.
    assert (
        "sentinel" in combined or "." in combined
    ), f"sentinel --version produced no usable output:\n{result.stdout}\n{result.stderr}"
