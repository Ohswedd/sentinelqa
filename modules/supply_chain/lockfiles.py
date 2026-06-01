"""Lockfile discovery + parsers.

Seven shapes are supported ( README):

- Python: ``uv.lock``, ``poetry.lock``, ``Pipfile.lock``, ``requirements.txt``
- Node: ``package-lock.json``, ``pnpm-lock.yaml``, ``yarn.lock``

Each parser is intentionally narrow — we read only the fields we need
(name, version, optional license, optional direct-vs-transitive marker).
We never run a resolver, never download package metadata, never execute
arbitrary code. Parser failures are recorded on
:class:`SbomLockfileResult.parse_error` and the run continues so a
single malformed lockfile cannot block the entire SBOM.

We deliberately accept plain stdlib + ``tomllib`` + ``yaml`` (which is
already a transitive dep across the project) rather than pull in the
ecosystem-specific resolver libraries — those bring in build hooks and
network code we don't want in a defensive audit module.
"""

from __future__ import annotations

import json
import re
import tomllib
import urllib.parse
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from modules.supply_chain.models import Ecosystem, LockfileKind, SbomComponent

# Mapping lockfile filename -> (kind, ecosystem). Order matters: the
# project-root walker yields paths in this order so the SBOM index is
# deterministic.
_KNOWN_LOCKFILES: Final[tuple[tuple[str, LockfileKind, Ecosystem], ...]] = (
    ("uv.lock", "uv.lock", "PyPI"),
    ("poetry.lock", "poetry.lock", "PyPI"),
    ("Pipfile.lock", "Pipfile.lock", "PyPI"),
    ("requirements.txt", "requirements.txt", "PyPI"),
    ("package-lock.json", "package-lock.json", "npm"),
    ("pnpm-lock.yaml", "pnpm-lock.yaml", "npm"),
    ("yarn.lock", "yarn.lock", "npm"),
)


@dataclass(frozen=True, slots=True)
class DetectedLockfile:
    """One lockfile discovered during the project-root walk."""

    path: Path
    kind: LockfileKind
    ecosystem: Ecosystem


def detect_lockfiles(project_root: Path) -> tuple[DetectedLockfile, ...]:
    """Walk ``project_root`` (non-recursive) for known lockfiles.

    keeps the walk shallow on purpose: a target app may vendor
    its dependencies under ``node_modules/`` or ``vendor/`` and we don't
    want to re-parse every nested lockfile (Trivy's job, not ours).
    The aggregate SBOM still captures every distinct ``name@version``
    that ends up in the project's direct lockfiles.
    """

    out: list[DetectedLockfile] = []
    for filename, kind, ecosystem in _KNOWN_LOCKFILES:
        candidate = project_root / filename
        if candidate.is_file():
            out.append(DetectedLockfile(path=candidate, kind=kind, ecosystem=ecosystem))
    return tuple(out)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _purl_for(ecosystem: Ecosystem, name: str, version: str) -> str:
    """Build a Package URL (purl) for the given component.

    https://github.com/package-url/purl-spec — we emit minimal but
    schema-valid purls (``pkg:pypi/<name>@<version>`` / ``pkg:npm/<name>@<version>``).
    The name is URL-encoded so we don't break on scoped packages (e.g.
    ``@scope/pkg`` becomes ``%40scope/pkg`` per the spec).
    """

    if ecosystem == "PyPI":
        scheme = "pypi"
        encoded_name = urllib.parse.quote(name.lower(), safe="-_.")
    else:  # npm
        scheme = "npm"
        # purl-spec preserves npm scoped package case but URL-encodes ``@``.
        if name.startswith("@"):
            scope, _, pkg = name[1:].partition("/")
            encoded_name = (
                f"%40{urllib.parse.quote(scope, safe='')}/{urllib.parse.quote(pkg, safe='')}"
            )
        else:
            encoded_name = urllib.parse.quote(name, safe="")
    encoded_version = urllib.parse.quote(version, safe="-._~+")
    return f"pkg:{scheme}/{encoded_name}@{encoded_version}"


def _dedup(components: Iterable[SbomComponent]) -> tuple[SbomComponent, ...]:
    """Dedup by (ecosystem, name lower-cased, version) preserving order."""

    seen: set[tuple[str, str, str]] = set()
    out: list[SbomComponent] = []
    for component in components:
        key = (component.ecosystem, component.name.lower(), component.version)
        if key in seen:
            continue
        seen.add(key)
        out.append(component)
    return tuple(out)


# ---------------------------------------------------------------------------
# Python parsers
# ---------------------------------------------------------------------------


def parse_uv_lock(path: Path) -> tuple[SbomComponent, ...]:
    """Parse ``uv.lock`` (TOML, uv >= 0.4 layout)."""

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    packages = data.get("package", [])
    if not isinstance(packages, list):
        return ()
    components: list[SbomComponent] = []
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        name = pkg.get("name")
        version = pkg.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            continue
        components.append(
            SbomComponent(
                name=name,
                version=version,
                ecosystem="PyPI",
                purl=_purl_for("PyPI", name, version),
                direct=False,
            )
        )
    return _dedup(components)


def parse_poetry_lock(path: Path) -> tuple[SbomComponent, ...]:
    """Parse ``poetry.lock`` (TOML, Poetry >= 1.5)."""

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    packages = data.get("package", [])
    if not isinstance(packages, list):
        return ()
    components: list[SbomComponent] = []
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        name = pkg.get("name")
        version = pkg.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            continue
        components.append(
            SbomComponent(
                name=name,
                version=version,
                ecosystem="PyPI",
                purl=_purl_for("PyPI", name, version),
                direct=False,
            )
        )
    return _dedup(components)


def parse_pipfile_lock(path: Path) -> tuple[SbomComponent, ...]:
    """Parse ``Pipfile.lock`` (Pipenv JSON layout).

    Both the ``default`` and ``develop`` blocks are included; ``develop``
    entries are still in the bundle so they belong in the SBOM.
    """

    data = json.loads(path.read_text(encoding="utf-8"))
    components: list[SbomComponent] = []
    for section in ("default", "develop"):
        block = data.get(section, {})
        if not isinstance(block, dict):
            continue
        for name, entry in block.items():
            if not isinstance(name, str) or not isinstance(entry, dict):
                continue
            version = entry.get("version")
            if not isinstance(version, str):
                continue
            # Pipenv stores versions as ``==1.2.3`` strings — strip the
            # comparator so the SBOM carries the bare version.
            cleaned = version.lstrip("=").strip()
            if not cleaned:
                continue
            components.append(
                SbomComponent(
                    name=name,
                    version=cleaned,
                    ecosystem="PyPI",
                    purl=_purl_for("PyPI", name, cleaned),
                    direct=section == "default",
                )
            )
    return _dedup(components)


_REQUIREMENTS_LINE_RE: Final[re.Pattern[str]] = re.compile(
    # Allow ``name`` or ``name[extras]`` followed by ``==version``. The
    # supply-chain audit only cares about pinned versions — anything
    # else (``>=`` ranges, ``git+`` URLs) is intentionally skipped so
    # we don't put unresolved data in the SBOM.
    r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_.,\-\s]*\])?\s*==\s*(?P<version>[A-Za-z0-9._+\-]+)\s*(?:;.*)?$"
)


def parse_requirements_txt(path: Path) -> tuple[SbomComponent, ...]:
    """Parse ``requirements.txt`` (only ``name==version`` pins).

    Range specifiers, environment markers, and editable installs are
    skipped — the SBOM only records resolved versions (per the
    README: "Parsers cover only the lockfile shape").
    """

    components: list[SbomComponent] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = _REQUIREMENTS_LINE_RE.match(line)
        if not match:
            continue
        name = match.group("name")
        version = match.group("version")
        components.append(
            SbomComponent(
                name=name,
                version=version,
                ecosystem="PyPI",
                purl=_purl_for("PyPI", name, version),
                direct=True,
            )
        )
    return _dedup(components)


# ---------------------------------------------------------------------------
# Node parsers
# ---------------------------------------------------------------------------


def parse_package_lock_json(path: Path) -> tuple[SbomComponent, ...]:
    """Parse ``package-lock.json`` (npm v7+ lockfileVersion 2/3).

    The walker reads only the ``packages`` map (lockfileVersion 2+). Old
    ``dependencies``-only lockfiles (lockfileVersion 1) are also handled
    via the legacy fallback at the bottom of the function.
    """

    data = json.loads(path.read_text(encoding="utf-8"))
    components: list[SbomComponent] = []

    packages = data.get("packages")
    if isinstance(packages, dict):
        for package_path, entry in packages.items():
            if package_path == "" or not isinstance(entry, dict):
                # The empty-key entry describes the root project itself —
                # exclude it from the SBOM.
                continue
            # package_path looks like ``node_modules/<name>`` or
            # ``node_modules/<scope>/<name>``. Strip the prefix and take
            # the longest remaining segment.
            name = entry.get("name")
            if not isinstance(name, str):
                name = _name_from_package_path(package_path)
            version = entry.get("version")
            if not isinstance(name, str) or not isinstance(version, str):
                continue
            license_field = entry.get("license")
            licenses = (license_field,) if isinstance(license_field, str) else ()
            components.append(
                SbomComponent(
                    name=name,
                    version=version,
                    ecosystem="npm",
                    purl=_purl_for("npm", name, version),
                    licenses=licenses,
                    direct=False,
                )
            )
        return _dedup(components)

    # Legacy lockfileVersion 1.
    dependencies = data.get("dependencies", {})
    if isinstance(dependencies, dict):
        for name, entry in dependencies.items():
            if not isinstance(entry, dict):
                continue
            version = entry.get("version")
            if not isinstance(name, str) or not isinstance(version, str):
                continue
            components.append(
                SbomComponent(
                    name=name,
                    version=version,
                    ecosystem="npm",
                    purl=_purl_for("npm", name, version),
                    direct=True,
                )
            )
    return _dedup(components)


def _name_from_package_path(package_path: str) -> str:
    parts = package_path.split("node_modules/")
    return parts[-1] if parts else package_path


def parse_pnpm_lock_yaml(path: Path) -> tuple[SbomComponent, ...]:
    """Parse ``pnpm-lock.yaml`` (pnpm v9 ``importers`` + ``packages`` layout)."""

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return ()
    components: list[SbomComponent] = []
    packages = data.get("packages", {})
    if isinstance(packages, dict):
        for key, entry in packages.items():
            if not isinstance(key, str):
                continue
            name, version = _split_pnpm_key(key, entry)
            if not name or not version:
                continue
            components.append(
                SbomComponent(
                    name=name,
                    version=version,
                    ecosystem="npm",
                    purl=_purl_for("npm", name, version),
                    direct=False,
                )
            )
    return _dedup(components)


def _split_pnpm_key(key: str, entry: Any) -> tuple[str | None, str | None]:
    """Pull (name, version) from a pnpm packages key.

    pnpm v9 keys look like ``/@scope/pkg@1.2.3`` or ``/lodash@4.17.21``;
    older v6 keys use ``/lodash/4.17.21``. The entry may also carry an
    explicit ``name`` + ``version`` field which always wins.
    """

    if isinstance(entry, dict):
        explicit_name = entry.get("name")
        explicit_version = entry.get("version")
        if isinstance(explicit_name, str) and isinstance(explicit_version, str):
            return explicit_name, explicit_version
    stripped = key.lstrip("/")
    # Strip dependency-peer suffix ``(react@18.0.0)``.
    base = stripped.split("(", 1)[0]
    if base.startswith("@"):
        scope, _, rest = base.partition("/")
        if "@" in rest:
            name_part, _, version = rest.rpartition("@")
            return f"{scope}/{name_part}", version
        return None, None
    if "@" in base:
        name, _, version = base.rpartition("@")
        return name, version
    # Legacy ``/name/version``.
    name, _, version = base.rpartition("/")
    return name or None, version or None


_YARN_ENTRY_RE: Final[re.Pattern[str]] = re.compile(
    # Yarn classic header: ``"foo@^1.0.0", "foo@^1.1.0":``. We take the
    # first quoted spec and use the bare name. Yarn berry (yarn.lock v2)
    # adds a ``__metadata`` block at the top which is skipped.
    r"^[\"']?(?P<spec>[^\"',:]+)[\"']?(?:,.*)?:\s*$"
)
_YARN_VERSION_RE: Final[re.Pattern[str]] = re.compile(r"^\s+version\s+[\"']([^\"']+)[\"']")


def parse_yarn_lock(path: Path) -> tuple[SbomComponent, ...]:
    """Parse ``yarn.lock`` (Yarn classic / berry — header + ``version:`` line)."""

    components: list[SbomComponent] = []
    current_name: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        if raw_line.startswith(" "):
            if current_name is None:
                continue
            version_match = _YARN_VERSION_RE.match(raw_line)
            if version_match is None:
                continue
            version = version_match.group(1)
            components.append(
                SbomComponent(
                    name=current_name,
                    version=version,
                    ecosystem="npm",
                    purl=_purl_for("npm", current_name, version),
                    direct=False,
                )
            )
            current_name = None
            continue
        if raw_line.startswith("__metadata"):
            current_name = None
            continue
        match = _YARN_ENTRY_RE.match(raw_line)
        if match is None:
            current_name = None
            continue
        spec = match.group("spec").strip()
        current_name = _name_from_yarn_spec(spec)
    return _dedup(components)


def _name_from_yarn_spec(spec: str) -> str | None:
    """``foo@^1.0.0`` → ``foo``; ``@scope/foo@^1.0.0`` → ``@scope/foo``."""

    if spec.startswith("@"):
        scope, _, rest = spec[1:].partition("/")
        name, _, _ = rest.partition("@")
        if not name:
            return None
        return f"@{scope}/{name}"
    name, _, _ = spec.partition("@")
    return name or None


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


_PARSERS = {
    "uv.lock": parse_uv_lock,
    "poetry.lock": parse_poetry_lock,
    "Pipfile.lock": parse_pipfile_lock,
    "requirements.txt": parse_requirements_txt,
    "package-lock.json": parse_package_lock_json,
    "pnpm-lock.yaml": parse_pnpm_lock_yaml,
    "yarn.lock": parse_yarn_lock,
}


def parse_lockfile(detected: DetectedLockfile) -> tuple[SbomComponent, ...]:
    """Run the parser registered for ``detected.kind``."""

    return _PARSERS[detected.kind](detected.path)


__all__ = [
    "DetectedLockfile",
    "detect_lockfiles",
    "parse_lockfile",
    "parse_package_lock_json",
    "parse_pipfile_lock",
    "parse_pnpm_lock_yaml",
    "parse_poetry_lock",
    "parse_requirements_txt",
    "parse_uv_lock",
    "parse_yarn_lock",
]
