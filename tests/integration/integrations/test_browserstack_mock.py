"""Mocked end-to-end test for ``integrations.browserstack``."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from integrations._http import (
    AuthHeader,
    HttpClient,
    IntegrationHttpError,
)
from integrations.browserstack import (
    BrowserStackQuotaExceeded,
    BrowserStackRunner,
    map_capabilities,
)
from integrations.browserstack.runner import (
    BROWSERSTACK_API,
    BROWSERSTACK_KEY_ENV,
    BROWSERSTACK_USER_ENV,
    BrowserStackConfigError,
    BrowserStackCredentials,
)


class _FakeClient(HttpClient):
    """Records every request so the test can assert on it."""

    def __init__(self, *, responses: list[Any] | None = None) -> None:
        super().__init__(auth=AuthHeader.basic("u", "k"))
        self._responses = list(responses or [])
        self.calls: list[tuple[str, str, Mapping[str, Any] | None]] = []

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: Mapping[str, Any] | None,
        parse_json: bool = True,
    ) -> Any:
        del parse_json
        self.calls.append((method, url, body))
        if not self._responses:
            raise AssertionError(f"unexpected {method} {url}: no scripted response")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


def test_credentials_from_env_reads_named_vars() -> None:
    env = {BROWSERSTACK_USER_ENV: "alice", BROWSERSTACK_KEY_ENV: "deadbeef"}
    creds = BrowserStackCredentials.from_env(environ=env)
    assert creds.username == "alice"
    assert creds.access_key == "deadbeef"


def test_credentials_from_env_strips_whitespace() -> None:
    env = {BROWSERSTACK_USER_ENV: "  alice  ", BROWSERSTACK_KEY_ENV: " key  "}
    creds = BrowserStackCredentials.from_env(environ=env)
    assert creds.username == "alice"
    assert creds.access_key == "key"


@pytest.mark.parametrize(
    "env",
    [
        {},
        {BROWSERSTACK_USER_ENV: "alice"},
        {BROWSERSTACK_KEY_ENV: "key"},
        {BROWSERSTACK_USER_ENV: "  ", BROWSERSTACK_KEY_ENV: "key"},
    ],
)
def test_credentials_from_env_refuses_missing(env: dict[str, str]) -> None:
    with pytest.raises(BrowserStackConfigError):
        BrowserStackCredentials.from_env(environ=env)


# ---------------------------------------------------------------------------
# Capability mapping
# ---------------------------------------------------------------------------


def test_map_capabilities_minimal_payload() -> None:
    caps = map_capabilities(browser="chromium", headless=True)
    assert caps["browser"] == "playwright-chromium"
    assert caps["headless"] is True
    options = caps["browserstack.options"]
    assert options["projectName"] == "sentinelqa"
    assert options["sessionName"] == "sentinelqa-chromium"
    assert options["local"] is False
    assert "buildName" not in options


def test_map_capabilities_with_build_and_viewport() -> None:
    caps = map_capabilities(
        browser="firefox",
        headless=False,
        build="run-123",
        name="login spec",
        viewport=(1280, 800),
        os_name="OS X",
        os_version="Sonoma",
    )
    assert caps["browser"] == "playwright-firefox"
    assert caps["headless"] is False
    options = caps["browserstack.options"]
    assert options["buildName"] == "run-123"
    assert options["sessionName"] == "login spec"
    assert options["os"] == "OS X"
    assert options["osVersion"] == "Sonoma"
    assert caps["viewport"] == {"width": 1280, "height": 800}


def test_map_capabilities_extra_overlays_last() -> None:
    caps = map_capabilities(
        browser="webkit",
        headless=True,
        extra={"browser_version": "16.6"},
    )
    assert caps["browser_version"] == "16.6"


def test_map_capabilities_rejects_unknown_browser() -> None:
    with pytest.raises(BrowserStackConfigError):
        map_capabilities(browser="ie", headless=True)


def test_map_capabilities_rejects_bad_viewport() -> None:
    with pytest.raises(BrowserStackConfigError):
        map_capabilities(browser="chromium", headless=True, viewport=(0, 800))


# ---------------------------------------------------------------------------
# Runner.run
# ---------------------------------------------------------------------------


def _creds() -> BrowserStackCredentials:
    return BrowserStackCredentials(username="alice", access_key="deadbeef")


def test_run_submits_session_and_uploads_traces() -> None:
    client = _FakeClient(
        responses=[
            # create-session
            {
                "automation_session": {
                    "hashed_id": "session-1",
                    "build_hashed_id": "build-1",
                }
            },
            # trace upload 1
            {"url": "https://bs.example/screenshots/1.png"},
            # trace upload 2
            {"url": "https://bs.example/screenshots/2.png"},
        ]
    )
    runner = BrowserStackRunner(credentials=_creds(), client=client)

    outcome = runner.run(
        {
            "browser": "chromium",
            "headless": True,
            "run_id": "RUN-2026-05-30-001",
            "test_name": "login",
            "trace_paths": ["t1.zip", "t2.zip"],
        },
        context=None,
    )

    assert outcome["status"] == "submitted"
    assert outcome["session_id"] == "session-1"
    assert outcome["build_id"] == "build-1"
    assert [t["url"] for t in outcome["traces"]] == [
        "https://bs.example/screenshots/1.png",
        "https://bs.example/screenshots/2.png",
    ]
    # All calls are scoped to api.browserstack.com — no other host.
    for _, url, _ in client.calls:
        assert url.startswith(BROWSERSTACK_API)
    # The first call is the create-session POST.
    method, url, body = client.calls[0]
    assert method == "POST"
    assert url == f"{BROWSERSTACK_API}/automate/sessions.json"
    assert body is not None
    submitted_caps = body["capabilities"]
    assert submitted_caps["browser"] == "playwright-chromium"
    assert submitted_caps["browserstack.options"]["buildName"] == "RUN-2026-05-30-001"


def test_run_quota_exceeded_on_session_creation_is_graceful() -> None:
    client = _FakeClient(responses=[IntegrationHttpError("POST x -> HTTP 429: quota")])
    runner = BrowserStackRunner(credentials=_creds(), client=client)
    outcome = runner.run({"browser": "chromium", "headless": True}, context=None)
    assert outcome["status"] == "quota_exceeded"
    assert outcome["session_id"] == ""
    assert outcome["traces"] == []


def test_run_quota_exceeded_mid_trace_upload_breaks_loop() -> None:
    client = _FakeClient(
        responses=[
            {"automation_session": {"hashed_id": "sess", "build_hashed_id": "b"}},
            {"url": "https://bs.example/s1.png"},
            IntegrationHttpError("POST x -> HTTP 429: quota"),
            # Third trace should NOT be requested.
        ]
    )
    runner = BrowserStackRunner(credentials=_creds(), client=client)
    outcome = runner.run(
        {
            "browser": "chromium",
            "headless": True,
            "trace_paths": ["t1.zip", "t2.zip", "t3.zip"],
        },
        context=None,
    )
    assert outcome["status"] == "submitted"
    assert len(outcome["traces"]) == 1
    # Two trace-upload calls were made (the second 429'd), third skipped.
    method_urls = [(m, u) for m, u, _ in client.calls]
    trace_calls = [u for m, u in method_urls if "/screenshots/upload.json" in u and m == "POST"]
    assert len(trace_calls) == 2


def test_run_non_quota_trace_failure_keeps_session_status() -> None:
    client = _FakeClient(
        responses=[
            {"automation_session": {"hashed_id": "sess", "build_hashed_id": "b"}},
            IntegrationHttpError("POST x -> HTTP 500: kaboom"),
        ]
    )
    runner = BrowserStackRunner(credentials=_creds(), client=client)
    outcome = runner.run(
        {"browser": "chromium", "headless": True, "trace_paths": ["t.zip"]},
        context=None,
    )
    assert outcome["status"] == "submitted"
    assert outcome["traces"] == []


def test_run_rejects_non_json_object_session_response() -> None:
    client = _FakeClient(responses=[["unexpected", "list"]])
    runner = BrowserStackRunner(credentials=_creds(), client=client)
    with pytest.raises(IntegrationHttpError):
        runner.run({"browser": "chromium", "headless": True}, context=None)


def test_run_rejects_session_response_missing_id() -> None:
    client = _FakeClient(responses=[{"automation_session": {}}])
    runner = BrowserStackRunner(credentials=_creds(), client=client)
    with pytest.raises(IntegrationHttpError):
        runner.run({"browser": "chromium", "headless": True}, context=None)


def test_quota_exceeded_propagates_when_constructed_directly() -> None:
    # Sanity: the exception class is part of the public surface.
    with pytest.raises(BrowserStackQuotaExceeded):
        raise BrowserStackQuotaExceeded("test")


def test_plugin_protocol_attrs_present() -> None:
    assert BrowserStackRunner.kind == "runner"
    assert BrowserStackRunner.name == "browserstack"
    assert "network.outbound" in BrowserStackRunner.permissions
    assert f"env.read:{BROWSERSTACK_USER_ENV}" in BrowserStackRunner.permissions
    assert f"env.read:{BROWSERSTACK_KEY_ENV}" in BrowserStackRunner.permissions
