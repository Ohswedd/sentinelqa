"""Mocked end-to-end test for ``integrations.saucelabs``."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from integrations._http import (
    AuthHeader,
    HttpClient,
    IntegrationHttpError,
)
from integrations.saucelabs import (
    SauceLabsQuotaExceeded,
    SauceLabsRunner,
    map_capabilities,
)
from integrations.saucelabs.runner import (
    SAUCE_KEY_ENV,
    SAUCE_USER_ENV,
    SauceLabsConfigError,
    SauceLabsCredentials,
)


class _FakeClient(HttpClient):
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


def _creds() -> SauceLabsCredentials:
    return SauceLabsCredentials(username="alice", access_key="deadbeef")


# Credentials ---------------------------------------------------------------


def test_credentials_from_env_reads_named_vars() -> None:
    env = {SAUCE_USER_ENV: "alice", SAUCE_KEY_ENV: "abc"}
    creds = SauceLabsCredentials.from_env(environ=env)
    assert creds.username == "alice"
    assert creds.access_key == "abc"


@pytest.mark.parametrize(
    "env",
    [
        {},
        {SAUCE_USER_ENV: "alice"},
        {SAUCE_KEY_ENV: "abc"},
        {SAUCE_USER_ENV: "  ", SAUCE_KEY_ENV: "abc"},
    ],
)
def test_credentials_from_env_refuses_missing(env: dict[str, str]) -> None:
    with pytest.raises(SauceLabsConfigError):
        SauceLabsCredentials.from_env(environ=env)


# Capability mapping --------------------------------------------------------


def test_map_capabilities_minimal_payload() -> None:
    caps = map_capabilities(browser="chromium", headless=True)
    assert caps["browserName"] == "chromium"
    assert caps["headless"] is True
    sopts = caps["sauce:options"]
    assert sopts["name"] == "sentinelqa-chromium"
    assert sopts["build"] == "sentinelqa-untagged"
    assert sopts["tags"] == ["sentinelqa"]


def test_map_capabilities_with_build_and_viewport() -> None:
    caps = map_capabilities(
        browser="webkit",
        headless=False,
        build="run-1",
        name="login",
        viewport=(1024, 768),
        tunnel_identifier="my-tunnel",
    )
    assert caps["browserName"] == "webkit"
    assert caps["headless"] is False
    sopts = caps["sauce:options"]
    assert sopts["name"] == "login"
    assert sopts["build"] == "run-1"
    assert sopts["tunnelIdentifier"] == "my-tunnel"
    assert caps["viewport"] == {"width": 1024, "height": 768}


def test_map_capabilities_extra_overrides_last() -> None:
    caps = map_capabilities(browser="firefox", headless=True, extra={"browserVersion": "120"})
    assert caps["browserVersion"] == "120"


def test_map_capabilities_rejects_unknown_browser() -> None:
    with pytest.raises(SauceLabsConfigError):
        map_capabilities(browser="edge", headless=True)


def test_map_capabilities_rejects_zero_viewport() -> None:
    with pytest.raises(SauceLabsConfigError):
        map_capabilities(browser="chromium", headless=True, viewport=(800, 0))


# Region --------------------------------------------------------------------


def test_runner_rejects_unknown_region() -> None:
    with pytest.raises(SauceLabsConfigError):
        SauceLabsRunner(credentials=_creds(), region="us-east-99")


def test_runner_accepts_eu_region() -> None:
    runner = SauceLabsRunner(credentials=_creds(), region="eu-central-1")
    assert "eu-central-1" in runner.api_base


# Run flow ------------------------------------------------------------------


def test_run_submits_job_and_uploads_artifacts() -> None:
    client = _FakeClient(
        responses=[
            {"id": "job-1"},
            {"name": "trace1.zip", "url": "https://sl/trace1"},
            {"name": "trace2.zip", "url": "https://sl/trace2"},
        ]
    )
    runner = SauceLabsRunner(credentials=_creds(), client=client)
    outcome = runner.run(
        {
            "browser": "chromium",
            "headless": True,
            "run_id": "RUN-1",
            "test_name": "smoke",
            "trace_paths": ["t1.zip", "t2.zip"],
        },
        context=None,
    )
    assert outcome["status"] == "submitted"
    assert outcome["job_id"] == "job-1"
    assert outcome["region"] == "us-west-1"
    assert [a["url"] for a in outcome["artifacts"]] == [
        "https://sl/trace1",
        "https://sl/trace2",
    ]
    # First call is POST to.../jobs scoped to the user.
    method, url, body = client.calls[0]
    assert method == "POST"
    assert url.endswith("/rest/v1/alice/jobs")
    assert body is not None
    assert body["capabilities"]["browserName"] == "chromium"


def test_run_quota_exceeded_on_job_create_returns_degraded() -> None:
    client = _FakeClient(responses=[IntegrationHttpError("POST x -> HTTP 429: quota")])
    runner = SauceLabsRunner(credentials=_creds(), client=client)
    outcome = runner.run({"browser": "chromium", "headless": True}, context=None)
    assert outcome["status"] == "quota_exceeded"
    assert outcome["job_id"] == ""


def test_run_quota_exceeded_mid_artifact_upload_breaks_loop() -> None:
    client = _FakeClient(
        responses=[
            {"id": "j"},
            {"name": "a.zip", "url": "u"},
            IntegrationHttpError("POST x -> HTTP 429: quota"),
        ]
    )
    runner = SauceLabsRunner(credentials=_creds(), client=client)
    outcome = runner.run(
        {
            "browser": "chromium",
            "headless": True,
            "trace_paths": ["a.zip", "b.zip", "c.zip"],
        },
        context=None,
    )
    assert outcome["status"] == "submitted"
    assert len(outcome["artifacts"]) == 1


def test_run_non_quota_artifact_failure_does_not_crash() -> None:
    client = _FakeClient(
        responses=[
            {"id": "j"},
            IntegrationHttpError("POST x -> HTTP 500: oops"),
        ]
    )
    runner = SauceLabsRunner(credentials=_creds(), client=client)
    outcome = runner.run(
        {"browser": "chromium", "headless": True, "trace_paths": ["a.zip"]},
        context=None,
    )
    assert outcome["status"] == "submitted"
    assert outcome["artifacts"] == []


def test_run_rejects_non_object_response() -> None:
    client = _FakeClient(responses=[["unexpected"]])
    runner = SauceLabsRunner(credentials=_creds(), client=client)
    with pytest.raises(IntegrationHttpError):
        runner.run({"browser": "chromium", "headless": True}, context=None)


def test_run_rejects_response_missing_id() -> None:
    client = _FakeClient(responses=[{}])
    runner = SauceLabsRunner(credentials=_creds(), client=client)
    with pytest.raises(IntegrationHttpError):
        runner.run({"browser": "chromium", "headless": True}, context=None)


def test_quota_exception_class_exposed() -> None:
    with pytest.raises(SauceLabsQuotaExceeded):
        raise SauceLabsQuotaExceeded("test")


def test_plugin_protocol_attrs_present() -> None:
    assert SauceLabsRunner.kind == "runner"
    assert SauceLabsRunner.name == "saucelabs"
    assert f"env.read:{SAUCE_USER_ENV}" in SauceLabsRunner.permissions
    assert f"env.read:{SAUCE_KEY_ENV}" in SauceLabsRunner.permissions
