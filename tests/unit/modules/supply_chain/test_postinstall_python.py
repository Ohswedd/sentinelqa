"""Postinstall scanner — Python AST patterns."""

from __future__ import annotations

from pathlib import Path

from modules.supply_chain.postinstall import scan_python_setup_py


def _write_setup(pkg_dir: Path, body: str) -> Path:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    path = pkg_dir / "setup.py"
    path.write_text(body, encoding="utf-8")
    return path


def test_scan_flags_subprocess_import(tmp_path: Path) -> None:
    setup_py = _write_setup(
        tmp_path / "evil",
        "import subprocess\nsubprocess.Popen(['curl', 'https://x'])\n",
    )
    issues = scan_python_setup_py(setup_py)
    assert any(issue.pattern == "import:subprocess" for issue in issues)
    assert any(issue.pattern == "call:subprocess.Popen" for issue in issues)


def test_scan_flags_urllib_request_import(tmp_path: Path) -> None:
    setup_py = _write_setup(
        tmp_path / "net",
        "import urllib.request\nurllib.request.urlopen('https://x')\n",
    )
    issues = scan_python_setup_py(setup_py)
    assert any(issue.pattern == "import:urllib.request" for issue in issues)


def test_scan_flags_from_urllib_request_import(tmp_path: Path) -> None:
    setup_py = _write_setup(
        tmp_path / "net2",
        "from urllib.request import urlopen\nurlopen('https://x')\n",
    )
    issues = scan_python_setup_py(setup_py)
    assert any(issue.pattern == "import:urllib.request" for issue in issues)


def test_scan_flags_requests_import(tmp_path: Path) -> None:
    setup_py = _write_setup(
        tmp_path / "r",
        "import requests\nrequests.get('https://x')\n",
    )
    issues = scan_python_setup_py(setup_py)
    assert any(issue.pattern == "import:requests" for issue in issues)


def test_scan_clean_setup_py(tmp_path: Path) -> None:
    setup_py = _write_setup(
        tmp_path / "clean",
        "from setuptools import setup\nsetup(name='clean', version='1.0.0')\n",
    )
    assert scan_python_setup_py(setup_py) == ()


def test_scan_handles_syntax_error(tmp_path: Path) -> None:
    setup_py = _write_setup(tmp_path / "broken", "import this\n!!!syntax!!!\n")
    assert scan_python_setup_py(setup_py) == ()


def test_scan_flags_os_system_call(tmp_path: Path) -> None:
    setup_py = _write_setup(tmp_path / "ossys", "import os\nos.system('curl evil')\n")
    issues = scan_python_setup_py(setup_py)
    assert any(issue.pattern == "call:os.system" for issue in issues)


def test_scan_handles_missing_file(tmp_path: Path) -> None:
    issues = scan_python_setup_py(tmp_path / "absent.py")
    assert issues == ()
