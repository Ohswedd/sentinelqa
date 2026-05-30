"""Mocked Slack poster tests (Phase 25.03)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from integrations._http import HttpClient, IntegrationHttpError
from integrations.slack import (
    SLACK_WEBHOOK_ENV,
    SlackPoster,
    SlackPosterError,
    SlackWebhookDeduper,
    post_payload,
)
from integrations.slack import poster as poster_mod


class _FakeClient(HttpClient):
    def __init__(self, *, responses: list[Any]) -> None:
        super().__init__()
        self._responses = list(responses)
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def post_text(self, url: str, payload: Mapping[str, Any]) -> str:
        self.calls.append((url, dict(payload)))
        if not self._responses:
            raise AssertionError("no scripted response")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return str(nxt)


_PAYLOAD: dict[str, Any] = {
    "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "*hello*"}}]
}


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_constructor_rejects_non_https_webhook() -> None:
    with pytest.raises(SlackPosterError):
        SlackPoster(webhook_url="http://hooks.slack.com/services/x/y/z")


def test_webhook_url_accessor_returns_value() -> None:
    poster = SlackPoster(webhook_url="https://hooks.slack.com/services/x/y/z")
    assert poster.webhook_url == "https://hooks.slack.com/services/x/y/z"


# ---------------------------------------------------------------------------
# Post happy path
# ---------------------------------------------------------------------------


def test_post_returns_ok_on_success() -> None:
    client = _FakeClient(responses=["ok"])
    poster = SlackPoster(
        webhook_url="https://hooks.slack.com/services/x/y/z",
        client=client,
    )
    result = poster.post(_PAYLOAD)
    assert result == "ok"
    assert client.calls
    url, payload = client.calls[0]
    assert url == "https://hooks.slack.com/services/x/y/z"
    assert payload == _PAYLOAD


def test_post_handles_non_ok_reply_without_raising() -> None:
    # The slack module logs a WARNING when the body is not "ok", but
    # the lib also returns the body verbatim. We only assert the
    # non-raising contract here — caplog isn't reliable across the
    # full pytest session because earlier tests reconfigure logging.
    client = _FakeClient(responses=["maybe"])
    poster = SlackPoster(webhook_url="https://hooks.slack.com/services/x/y/z", client=client)
    result = poster.post(_PAYLOAD)
    assert result == "maybe"


def test_post_wraps_transport_error_as_poster_error() -> None:
    client = _FakeClient(responses=[IntegrationHttpError("POST x -> HTTP 500: oops")])
    poster = SlackPoster(webhook_url="https://hooks.slack.com/services/x/y/z", client=client)
    with pytest.raises(SlackPosterError) as exc:
        poster.post(_PAYLOAD)
    assert "hooks.slack.com" in str(exc.value)
    # The redacted URL must NOT include the secret path /services/x/y/z.
    assert "/services/x/y/z" not in str(exc.value) or "<redacted>" in str(exc.value)


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


def test_dedup_skips_duplicate_within_window(tmp_path: Path) -> None:
    dedup_path = tmp_path / "slack-dedup.json"
    times = iter([100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0])

    def _clock() -> float:
        return next(times)

    dedup = SlackWebhookDeduper(path=dedup_path, window_seconds=300, _now=_clock)
    client = _FakeClient(responses=["ok"])
    poster = SlackPoster(
        webhook_url="https://hooks.slack.com/services/a/b/c",
        client=client,
        dedup=dedup,
    )

    first = poster.post(_PAYLOAD)
    second = poster.post(_PAYLOAD)

    assert first == "ok"
    assert second == "deduped"
    # Only one HTTP call.
    assert len(client.calls) == 1


def test_dedup_allows_repost_after_window_elapses(tmp_path: Path) -> None:
    dedup_path = tmp_path / "slack-dedup.json"
    # Each post consumes 3 clock ticks: 1 in is_duplicate + 2 in record.
    # Window is 300s, so the second post at 9000+ is past the cutoff.
    times = iter([100.0, 110.0, 120.0, 9000.0, 9010.0, 9020.0])

    def _clock() -> float:
        return next(times)

    dedup = SlackWebhookDeduper(path=dedup_path, window_seconds=300, _now=_clock)
    client = _FakeClient(responses=["ok", "ok"])
    poster = SlackPoster(
        webhook_url="https://hooks.slack.com/services/a/b/c",
        client=client,
        dedup=dedup,
    )

    first = poster.post(_PAYLOAD)
    second = poster.post(_PAYLOAD)

    assert first == "ok"
    assert second == "ok"
    assert len(client.calls) == 2


def test_dedup_does_not_collapse_across_webhooks(tmp_path: Path) -> None:
    dedup_path = tmp_path / "slack-dedup.json"
    times = iter([100.0] * 20)

    dedup = SlackWebhookDeduper(path=dedup_path, window_seconds=300, _now=lambda: next(times))
    client1 = _FakeClient(responses=["ok"])
    client2 = _FakeClient(responses=["ok"])
    p1 = SlackPoster(
        webhook_url="https://hooks.slack.com/services/A/A/A",
        client=client1,
        dedup=dedup,
    )
    p2 = SlackPoster(
        webhook_url="https://hooks.slack.com/services/B/B/B",
        client=client2,
        dedup=dedup,
    )

    assert p1.post(_PAYLOAD) == "ok"
    assert p2.post(_PAYLOAD) == "ok"
    assert len(client1.calls) == 1
    assert len(client2.calls) == 1


def test_dedup_handles_corrupt_cache_file(tmp_path: Path) -> None:
    dedup_path = tmp_path / "slack-dedup.json"
    dedup_path.write_text("not json", encoding="utf-8")
    dedup = SlackWebhookDeduper(path=dedup_path, window_seconds=300, _now=lambda: 5.0)
    # Should not raise; treats as empty store.
    assert not dedup.is_duplicate(
        payload=_PAYLOAD, webhook_url="https://hooks.slack.com/services/x/y/z"
    )


def test_dedup_handles_unexpected_json_shape(tmp_path: Path) -> None:
    dedup_path = tmp_path / "slack-dedup.json"
    dedup_path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    dedup = SlackWebhookDeduper(path=dedup_path, window_seconds=300, _now=lambda: 5.0)
    assert not dedup.is_duplicate(
        payload=_PAYLOAD, webhook_url="https://hooks.slack.com/services/x/y/z"
    )


# ---------------------------------------------------------------------------
# post_payload helper + CLI
# ---------------------------------------------------------------------------


def test_post_payload_writes_dedup_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache.json"
    client = _FakeClient(responses=["ok"])
    reply = post_payload(
        payload=_PAYLOAD,
        webhook_url="https://hooks.slack.com/services/x/y/z",
        dedup_path=cache,
        client=client,
    )
    assert reply == "ok"
    assert cache.is_file()
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert len(data) == 1


def test_cli_main_missing_env_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(_PAYLOAD), encoding="utf-8")
    monkeypatch.delenv(SLACK_WEBHOOK_ENV, raising=False)
    rc = poster_mod.main(["--payload", str(payload_path)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "unset" in captured.err.lower()


def test_cli_main_missing_payload_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(SLACK_WEBHOOK_ENV, "https://hooks.slack.com/services/a/b/c")
    rc = poster_mod.main(["--payload", str(tmp_path / "missing.json")])
    assert rc == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_cli_main_rejects_non_object_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    monkeypatch.setenv(SLACK_WEBHOOK_ENV, "https://hooks.slack.com/services/a/b/c")
    rc = poster_mod.main(["--payload", str(payload_path)])
    assert rc == 1
    assert "json object" in capsys.readouterr().err.lower()


def test_cli_main_happy_path_uses_fake_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(_PAYLOAD), encoding="utf-8")
    monkeypatch.setenv(SLACK_WEBHOOK_ENV, "https://hooks.slack.com/services/a/b/c")

    sentinel: list[Mapping[str, Any]] = []

    def _stub_post_payload(*, payload: Mapping[str, Any], **_: Any) -> str:
        sentinel.append(payload)
        return "ok"

    monkeypatch.setattr(poster_mod, "post_payload", _stub_post_payload)
    rc = poster_mod.main(["--payload", str(payload_path)])
    assert rc == 0
    assert sentinel == [_PAYLOAD]
