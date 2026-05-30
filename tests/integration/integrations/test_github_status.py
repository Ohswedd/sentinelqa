"""Mocked tests for ``integrations.github.status`` (Phase 25.04)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from integrations._http import AuthHeader, HttpClient, IntegrationHttpError
from integrations.github import status as status_mod
from integrations.github.status import (
    DEFAULT_CONTEXT,
    GITHUB_API,
    GitHubStatusError,
    post_commit_status,
)


class _FakeClient(HttpClient):
    def __init__(self, *, responses: list[Any]) -> None:
        super().__init__(auth=AuthHeader.bearer("t"))
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


def test_post_commit_status_happy_path() -> None:
    client = _FakeClient(responses=[{"url": "https://api.github.com/x", "state": "success"}])
    response = post_commit_status(
        repo="ohswedd/sentinelqa",
        sha="abc123",
        state="success",
        description="quality_score=92, decision=pass",
        target_url="https://example/report.html",
        client=client,
    )
    assert response["state"] == "success"
    method, url, body = client.calls[0]
    assert method == "POST"
    assert url == f"{GITHUB_API}/repos/ohswedd/sentinelqa/statuses/abc123"
    assert body is not None
    assert body["state"] == "success"
    assert body["description"] == "quality_score=92, decision=pass"
    assert body["context"] == DEFAULT_CONTEXT
    assert body["target_url"] == "https://example/report.html"


def test_description_is_clipped_at_140_chars() -> None:
    client = _FakeClient(responses=[{}])
    desc = "x" * 500
    post_commit_status(
        repo="o/r",
        sha="sha",
        state="pending",
        description=desc,
        client=client,
    )
    body = client.calls[0][2]
    assert body is not None
    assert len(body["description"]) == 140


@pytest.mark.parametrize("state", ["", "ok", "blocked", "succes"])
def test_post_commit_status_rejects_invalid_state(state: str) -> None:
    with pytest.raises(GitHubStatusError):
        post_commit_status(
            repo="o/r",
            sha="sha",
            state=state,  # type: ignore[arg-type]
            description="x",
            client=_FakeClient(responses=[]),
        )


def test_post_commit_status_rejects_bad_repo_slug() -> None:
    with pytest.raises(GitHubStatusError):
        post_commit_status(
            repo="no-slash",
            sha="abc",
            state="success",
            description="x",
            client=_FakeClient(responses=[]),
        )


def test_post_commit_status_rejects_empty_sha() -> None:
    with pytest.raises(GitHubStatusError):
        post_commit_status(
            repo="o/r",
            sha="",
            state="success",
            description="x",
            client=_FakeClient(responses=[]),
        )


def test_post_commit_status_wraps_transport_error() -> None:
    client = _FakeClient(responses=[IntegrationHttpError("POST -> HTTP 500: x")])
    with pytest.raises(GitHubStatusError):
        post_commit_status(
            repo="o/r",
            sha="abc",
            state="success",
            description="x",
            client=client,
        )


def test_post_commit_status_rejects_non_json_object_response() -> None:
    client = _FakeClient(responses=[["unexpected"]])
    with pytest.raises(GitHubStatusError):
        post_commit_status(
            repo="o/r",
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
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    rc = status_mod.main(
        [
            "--repo",
            "o/r",
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
    monkeypatch.setenv("GITHUB_TOKEN", "tk")
    captured: dict[str, Any] = {}

    def _stub_post(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"url": "https://api.github.com/x"}

    monkeypatch.setattr(status_mod, "post_commit_status", _stub_post)
    rc = status_mod.main(
        [
            "--repo",
            "o/r",
            "--sha",
            "abc",
            "--state",
            "success",
            "--description",
            "ok",
            "--target-url",
            "https://example/x",
        ]
    )
    assert rc == 0
    assert captured["state"] == "success"
    assert captured["sha"] == "abc"
    assert captured["target_url"] == "https://example/x"
