"""Tests for the fixture generator."""

from __future__ import annotations

from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.ids import IdGenerator
from engine.generator.fixtures import FixtureGenerationOptions, generate_fixtures


def _opts(**kw: object) -> FixtureGenerationOptions:
    defaults = dict(
        base_url="https://staging.example.com/",
        login_url="https://staging.example.com/login",
        username_env="SENTINEL_USER",
        password_env="SENTINEL_PASS",
        security_mode="safe",
    )
    defaults.update(kw)
    return FixtureGenerationOptions(**defaults)


def test_emits_auth_and_setup_when_credentials_named() -> None:
    out = generate_fixtures(_opts())
    rel_paths = sorted(f.rel_path.as_posix() for f in out)
    assert "fixtures/auth.ts" in rel_paths
    assert "setup/global-setup.ts" in rel_paths
    assert "setup/global-teardown.ts" in rel_paths


def test_skips_auth_when_credentials_missing() -> None:
    out = generate_fixtures(_opts(login_url=None))
    rel_paths = [f.rel_path.as_posix() for f in out]
    assert "fixtures/auth.ts" not in rel_paths


def test_credentials_are_referenced_by_env_name_not_value() -> None:
    out = generate_fixtures(_opts())
    auth = next(f for f in out if f.kind == "auth")
    # Env-var names appear (referenced); raw passwords never do.
    assert "SENTINEL_USER" in auth.source
    assert "SENTINEL_PASS" in auth.source
    assert "process.env[USERNAME_ENV]" in auth.source


def test_data_fixture_emitted_when_creatable_endpoint_present() -> None:
    ids = IdGenerator()
    ep = ApiEndpoint(
        id=ids.new("API"),
        path="/api/users",
        method="POST",
        source="discovered",
    )
    out = generate_fixtures(_opts(), api_endpoints=[ep])
    rel_paths = [f.rel_path.as_posix() for f in out]
    assert "fixtures/data.ts" in rel_paths
    data_src = next(f for f in out if f.kind == "data").source
    # Data fixture gates on security mode AT RUNTIME (we cannot trust
    # the generator-time mode because the user may run elsewhere).
    assert "SAFE_MODES" in data_src
    assert "authorized_destructive" in data_src


def test_data_fixture_not_emitted_for_non_user_endpoint() -> None:
    ids = IdGenerator()
    ep = ApiEndpoint(
        id=ids.new("API"),
        path="/api/posts",
        method="POST",
        source="discovered",
    )
    out = generate_fixtures(_opts(), api_endpoints=[ep])
    # Path doesn't match the user-create heuristic and no override given.
    assert all(f.kind != "data" for f in out)


def test_explicit_user_create_endpoint_override() -> None:
    ids = IdGenerator()
    ep = ApiEndpoint(
        id=ids.new("API"),
        path="/v2/accounts",
        method="POST",
        source="openapi",
    )
    out = generate_fixtures(_opts(user_create_endpoint="/v2/accounts"), api_endpoints=[ep])
    assert any(f.kind == "data" for f in out)


def test_output_is_sorted_for_byte_stability() -> None:
    out = generate_fixtures(_opts())
    rels = [f.rel_path.as_posix() for f in out]
    assert rels == sorted(rels)


def test_no_credentials_committed_to_generated_source() -> None:
    out = generate_fixtures(_opts())
    for f in out:
        assert "Sentinel-secret-value" not in f.source  # paranoia anchor
        # Banner present so writer detects ownership.
        assert "SentinelQA Generated" in f.source
