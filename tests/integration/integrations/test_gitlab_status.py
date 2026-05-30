"""Mocked tests for ``integrations.gitlab.status`` (Phase 25.05)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from integrations._http import AuthHeader, HttpClient, IntegrationHttpError
from integrations.gitlab import status as status_mod
from integrations.gitlab.status import (
    DEFAULT_API_URL,
    DEFAULT_NAME,
    GitLabStatusError,
    post_commit_status,
)


class _FakeClient(HttpClient):
    def __init__(self, *, responses: list[Any]) -> None:
        super().__init__(auth=AuthHeader.header("PRIVATE-TOKEN", "t"))
        self._responses = list(responses)
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
            raise AssertionError(f"unexpected {method} {url}")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


# ---------------------------------------------------------------------------


def test_post_commit_status_happy_path_numeric_project_id() -> None:
    client = _FakeClient(responses=[{"id": 1, "ref": "main", "status": "success"}])
    response = post_commit_status(
        api_url=DEFAULT_API_URL,
        project="42",
        sha="deadbeef",
        state="success",
        description="quality_score=92",
        target_url="https://example/report.html",
        client=client,
    )
    assert response["status"] == "success"
    method, url, body = client.calls[0]
    assert method == "POST"
    assert url == f"{DEFAULT_API_URL}/projects/42/statuses/deadbeef"
    assert body is not None
    assert body["state"] == "success"
    assert body["name"] == DEFAULT_NAME
    assert body["description"] == "quality_score=92"
    assert body["target_url"] == "https://example/report.html"


def test_post_commit_status_url_encodes_namespaced_project() -> None:
    client = _FakeClient(responses=[{"id": 1}])
    post_commit_status(
        api_url=DEFAULT_API_URL,
        project="group/sub/repo",
        sha="abc",
        state="pending",
        description="x",
        client=client,
    )
    url = client.calls[0][1]
    assert "/projects/group%2Fsub%2Frepo/" in url


def test_description_clipped_at_255() -> None:
    client = _FakeClient(responses=[{}])
    post_commit_status(
        api_url=DEFAULT_API_URL,
        project="42",
        sha="abc",
        state="success",
        description="x" * 1000,
        client=client,
    )
    body = client.calls[0][2]
    assert body is not None
    assert len(body["description"]) == 255


@pytest.mark.parametrize("state", ["", "ok", "blocked", "succes"])
def test_post_commit_status_rejects_invalid_state(state: str) -> None:
    with pytest.raises(GitLabStatusError):
        post_commit_status(
            api_url=DEFAULT_API_URL,
            project="42",
            sha="abc",
            state=state,  # type: ignore[arg-type]
            description="x",
            client=_FakeClient(responses=[]),
        )


def test_post_commit_status_rejects_empty_project() -> None:
    with pytest.raises(GitLabStatusError):
        post_commit_status(
            api_url=DEFAULT_API_URL,
            project="",
            sha="abc",
            state="success",
            description="x",
            client=_FakeClient(responses=[]),
        )


def test_post_commit_status_rejects_empty_sha() -> None:
    with pytest.raises(GitLabStatusError):
        post_commit_status(
            api_url=DEFAULT_API_URL,
            project="42",
            sha="",
            state="success",
            description="x",
            client=_FakeClient(responses=[]),
        )


def test_post_commit_status_wraps_transport_error() -> None:
    client = _FakeClient(responses=[IntegrationHttpError("POST -> HTTP 500: x")])
    with pytest.raises(GitLabStatusError):
        post_commit_status(
            api_url=DEFAULT_API_URL,
            project="42",
            sha="abc",
            state="success",
            description="x",
            client=client,
        )


def test_post_commit_status_rejects_non_json_object_response() -> None:
    client = _FakeClient(responses=[["unexpected"]])
    with pytest.raises(GitLabStatusError):
        post_commit_status(
            api_url=DEFAULT_API_URL,
            project="42",
            sha="abc",
            state="success",
            description="x",
            client=client,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_main_missing_env_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    rc = status_mod.main(
        [
            "--project",
            "42",
            "--sha",
            "abc",
            "--state",
            "success",
            "--description",
            "ok",
        ]
    )
    assert rc == 1
    assert "empty" in capsys.readouterr().err.lower()


def test_cli_main_happy_path_uses_stubbed_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", "tk")
    captured: dict[str, Any] = {}

    def _stub_post(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ref": "main"}

    monkeypatch.setattr(status_mod, "post_commit_status", _stub_post)
    rc = status_mod.main(
        [
            "--project",
            "42",
            "--sha",
            "abc",
            "--state",
            "running",
            "--description",
            "ok",
        ]
    )
    assert rc == 0
    assert captured["state"] == "running"
    assert captured["project"] == "42"
