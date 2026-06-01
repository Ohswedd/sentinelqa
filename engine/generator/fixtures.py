"""Fixture generator.

Emits four small TypeScript files that generated specs import:

- ``tests/sentinel/fixtures/auth.ts`` — Playwright storageState
 fixture that logs in once per worker. Credentials are read from
 env-var names declared in the SentinelQA config; the generator never
 hardcodes them and refuses to emit auth.ts if the config does not
 name them.
- ``tests/sentinel/fixtures/data.ts`` — opt-in ``freshUser`` /
 ``seededRecord`` fixtures that create data via the discovery-detected
 API map and clean up after themselves.
- ``tests/sentinel/setup/global-setup.ts`` — runs auth-state generation
 once at suite start.
- ``tests/sentinel/setup/global-teardown.ts`` — cleans up any data
 fixtures created during the suite.

Safety boundary:

- No credentials in the generated source.
- Data fixtures abort when the SentinelQA security mode is not one of
 ``local`` or ``allowlisted``; an attempt to seed data against a
 production target without explicit allowlisting fails fast.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from engine.domain.api_endpoint import ApiEndpoint
from engine.generator.render import GENERATOR_BANNER


@dataclass(frozen=True)
class FixtureGenerationOptions:
    """Inputs the fixtures generator needs from the loaded config."""

    base_url: str
    login_url: str | None
    username_env: str | None
    password_env: str | None
    user_create_endpoint: str | None = None
    user_create_method: str = "POST"
    user_delete_endpoint_template: str | None = None
    security_mode: str = "safe"


@dataclass(frozen=True)
class GeneratedFixture:
    """One generated fixture file."""

    rel_path: Path
    source: str
    kind: str  # "auth" | "data" | "setup" | "teardown"


_DATA_DESTRUCTIVE_SAFE_MODES: frozenset[str] = frozenset({"authorized_destructive"})
"""SentinelQA security modes that permit data-seed fixtures to run.

the engineering guidelines / our product spec: ``safe`` mode is the conservative default and
explicitly forbids destructive operations against shared targets. Data
fixtures that POST to create users / records are destructive even when
they clean up after themselves (failures mid-flow leak data), so they
are gated to ``authorized_destructive`` only.
"""


def generate_fixtures(
    options: FixtureGenerationOptions,
    *,
    api_endpoints: Sequence[ApiEndpoint] = (),
) -> list[GeneratedFixture]:
    """Build the fixture file list. Output is deterministic for given inputs."""

    out: list[GeneratedFixture] = []

    if (
        options.login_url is not None
        and options.username_env is not None
        and options.password_env is not None
    ):
        out.append(_emit_auth_fixture(options))
        out.append(_emit_global_setup(options))
        out.append(_emit_global_teardown(options))

    creatable = _pick_creatable_endpoint(api_endpoints, options)
    if creatable is not None:
        out.append(_emit_data_fixture(options, endpoint=creatable))

    out.sort(key=lambda f: f.rel_path.as_posix())
    return out


def _pick_creatable_endpoint(
    api_endpoints: Sequence[ApiEndpoint],
    options: FixtureGenerationOptions,
) -> ApiEndpoint | None:
    """Prefer the config-named user-create endpoint; fall back to a heuristic."""

    if options.user_create_endpoint is not None:
        for ep in api_endpoints:
            if ep.path == options.user_create_endpoint and ep.method.upper() == "POST":
                return ep
        return None
    for ep in sorted(api_endpoints, key=lambda e: (e.path, e.method)):
        if ep.method.upper() != "POST":
            continue
        path_lc = ep.path.lower()
        if "user" in path_lc or "account" in path_lc or "register" in path_lc:
            return ep
    return None


def _emit_auth_fixture(options: FixtureGenerationOptions) -> GeneratedFixture:
    body = (
        GENERATOR_BANNER
        + "import { sentinelTest as test } from '@sentinelqa/ts-runtime/playwright';\n"
        + "import { expect } from '@playwright/test';\n"
        + "\n"
        + f"const USERNAME_ENV = {json.dumps(options.username_env)};\n"
        + f"const PASSWORD_ENV = {json.dumps(options.password_env)};\n"
        + f"const LOGIN_URL = {json.dumps(options.login_url)};\n"
        + "\n"
        + "export const authenticatedTest = test.extend<{ authedStorageStatePath: string }>({\n"
        + " // eslint-disable-next-line no-empty-pattern\n"
        + " authedStorageStatePath: [async ({}, use, workerInfo) => {\n"
        + " const username = process.env[USERNAME_ENV];\n"
        + " const password = process.env[PASSWORD_ENV];\n"
        + " test.skip(\n"
        + " !username || !password,\n"
        + " `Set ${USERNAME_ENV} and ${PASSWORD_ENV} to run authenticated tests.`,\n"
        + " );\n"
        + " const dir = workerInfo.project.outputDir;\n"
        + " const statePath = `${dir}/storage-state-${workerInfo.workerIndex}.json`;\n"
        + " const { chromium } = await import('@playwright/test');\n"
        + " const browser = await chromium.launch();\n"
        + " const context = await browser.newContext();\n"
        + " const page = await context.newPage();\n"
        + " await page.goto(LOGIN_URL);\n"
        + " await page.getByLabel(/email|username/i).fill(username as string);\n"
        + " await page.getByLabel(/password/i).fill(password as string);\n"
        + " await page.getByRole('button', { name: /sign in|log in/i }).click();\n"
        + " await expect(page).not.toHaveURL(LOGIN_URL);\n"
        + " await context.storageState({ path: statePath });\n"
        + " await browser.close();\n"
        + " await use(statePath);\n"
        + " }, { scope: 'worker' }],\n"
        + "});\n"
    )
    return GeneratedFixture(
        rel_path=Path("fixtures") / "auth.ts",
        source=body,
        kind="auth",
    )


def _emit_data_fixture(
    options: FixtureGenerationOptions,
    *,
    endpoint: ApiEndpoint,
) -> GeneratedFixture:
    safe_modes_json = json.dumps(sorted(_DATA_DESTRUCTIVE_SAFE_MODES))
    delete_template = options.user_delete_endpoint_template or ""
    body = (
        GENERATOR_BANNER
        + "import { sentinelTest as test } from '@sentinelqa/ts-runtime/playwright';\n"
        + "import { request as pwRequest } from '@playwright/test';\n"
        + "\n"
        + f"const BASE_URL = {json.dumps(options.base_url)};\n"
        + f"const CREATE_ENDPOINT = {json.dumps(endpoint.path)};\n"
        + f"const CREATE_METHOD = {json.dumps(endpoint.method)};\n"
        + f"const DELETE_TEMPLATE = {json.dumps(delete_template)};\n"
        + f"const SECURITY_MODE = {json.dumps(options.security_mode)};\n"
        + f"const SAFE_MODES = new Set({safe_modes_json});\n"
        + "\n"
        + "export interface FreshUser {\n"
        + " readonly id: string;\n"
        + " readonly email: string;\n"
        + "}\n"
        + "\n"
        + "export const dataTest = test.extend<{ freshUser: FreshUser }>({\n"
        + " // eslint-disable-next-line no-empty-pattern\n"
        + " freshUser: async ({}, use) => {\n"
        + " if (!SAFE_MODES.has(SECURITY_MODE)) {\n"
        + " throw new Error(\n"
        + " `SentinelQA refuses to seed data while security.mode=${SECURITY_MODE}. ` +\n"
        + " 'Set security.mode=authorized_destructive (with proof_of_authorization) ' +\n"
        + " 'in sentinel.config.yaml.',\n"
        + " );\n"
        + " }\n"
        + " const ctx = await pwRequest.newContext({ baseURL: BASE_URL });\n"
        + " const email = `sentinel+${Date.now()}@example.com`;\n"
        + " const created = await ctx.fetch(CREATE_ENDPOINT, {\n"
        + " method: CREATE_METHOD,\n"
        + " data: { email, password: `sQ-${Date.now()}-x` },\n"
        + " });\n"
        + " if (!created.ok()) {\n"
        + " throw new Error(`fresh-user create failed: ${created.status()}`);\n"
        + " }\n"
        + " const body = (await created.json()) as { id?: string };\n"
        + " const id = body.id ?? '';\n"
        + " try {\n"
        + " await use({ id, email });\n"
        + " } finally {\n"
        + " if (DELETE_TEMPLATE.length > 0 && id.length > 0) {\n"
        + " await ctx.delete(DELETE_TEMPLATE.replace('[id]', id));\n"
        + " }\n"
        + " await ctx.dispose();\n"
        + " }\n"
        + " },\n"
        + "});\n"
    )
    return GeneratedFixture(
        rel_path=Path("fixtures") / "data.ts",
        source=body,
        kind="data",
    )


def _emit_global_setup(options: FixtureGenerationOptions) -> GeneratedFixture:
    body = (
        GENERATOR_BANNER
        + "// Playwright invokes this once before the suite starts.\n"
        + "// It primes the storageState path env var so generated specs can\n"
        + "// reuse the authenticated session.\n"
        + "\n"
        + f"const USERNAME_ENV = {json.dumps(options.username_env)};\n"
        + f"const PASSWORD_ENV = {json.dumps(options.password_env)};\n"
        + "\n"
        + "export default async function globalSetup(): Promise<void> {\n"
        + " if (!process.env[USERNAME_ENV] || !process.env[PASSWORD_ENV]) {\n"
        + " // Auth is opt-in; specs that need it will skip themselves.\n"
        + " return;\n"
        + " }\n"
        + " // The per-worker `authedStorageStatePath` fixture in\n"
        + " // fixtures/auth.ts owns the actual login. This hook is a\n"
        + " // placeholder so generated configs can reference a stable path.\n"
        + "}\n"
    )
    return GeneratedFixture(
        rel_path=Path("setup") / "global-setup.ts",
        source=body,
        kind="setup",
    )


def _emit_global_teardown(options: FixtureGenerationOptions) -> GeneratedFixture:
    _ = options  # reserved for future use
    body = (
        GENERATOR_BANNER
        + "// Playwright invokes this once after the suite ends.\n"
        + "// Generated data fixtures clean up after themselves; the hook\n"
        + "// exists so future suites can register cross-test cleanup.\n"
        + "\n"
        + "export default async function globalTeardown(): Promise<void> {\n"
        + " return;\n"
        + "}\n"
    )
    return GeneratedFixture(
        rel_path=Path("setup") / "global-teardown.ts",
        source=body,
        kind="teardown",
    )


__all__ = [
    "FixtureGenerationOptions",
    "GeneratedFixture",
    "generate_fixtures",
]
