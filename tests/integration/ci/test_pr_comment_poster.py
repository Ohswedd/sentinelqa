"""Integration tests for the GitHub PR comment poster (task 17.03).

Strategy: load the poster module directly (it is invoked as a script
from the composite Action), substitute a fake ``HttpClient`` that
records calls, and exercise the upsert + retry paths end-to-end.

our engineering rules enforcement: a regression-style test asserts the
``Authorization`` header value never leaks into log records.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module(name: str, relative_path: str) -> ModuleType:
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


GH_POSTER = _load_module(
    "sentinelqa_test_post_pr_comment",
    "integrations/github/post_pr_comment.py",
)
GL_POSTER = _load_module(
    "sentinelqa_test_post_mr_note",
    "integrations/gitlab/post_mr_note.py",
)


class _RecordedCall:
    def __init__(self, method: str, url: str, body: dict[str, Any] | None) -> None:
        self.method = method
        self.url = url
        self.body = body


class _FakeResponse:
    """Tiny stand-in for the urlopen context manager."""

    def __init__(self, payload: Any) -> None:
        self._raw = b"" if payload is None else __import__("json").dumps(payload).encode()

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


def _install_fake_transport(
    monkeypatch: pytest.MonkeyPatch,
    *,
    module: ModuleType,
    responses: list[Any],
    calls: list[_RecordedCall],
) -> None:
    """Replace ``urllib.request.urlopen`` in the poster module's namespace."""

    queue = list(responses)

    def _fake_urlopen(request: Any, timeout: float | None = None) -> Any:
        method = request.get_method()
        url = request.full_url
        body_raw = request.data
        body = None
        if body_raw is not None:
            body = __import__("json").loads(body_raw.decode("utf-8"))
        calls.append(_RecordedCall(method, url, body))
        if not queue:
            raise AssertionError(f"unexpected extra request: {method} {url}")
        next_value = queue.pop(0)
        if isinstance(next_value, Exception):
            raise next_value
        return _FakeResponse(next_value)

    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        _fake_urlopen,
    )


def _make_github_client(
    monkeypatch: pytest.MonkeyPatch, responses: list[Any]
) -> tuple[Any, list[_RecordedCall]]:
    calls: list[_RecordedCall] = []
    _install_fake_transport(monkeypatch, module=GH_POSTER, responses=responses, calls=calls)
    client = GH_POSTER.HttpClient(token="ghp_fake_test_token")
    return client, calls


def _make_gitlab_client(
    monkeypatch: pytest.MonkeyPatch, responses: list[Any]
) -> tuple[Any, list[_RecordedCall]]:
    calls: list[_RecordedCall] = []
    _install_fake_transport(monkeypatch, module=GL_POSTER, responses=responses, calls=calls)
    client = GL_POSTER.HttpClient(token="glpat_fake_test_token")
    return client, calls


def _comment_body() -> str:
    body = GH_POSTER.PR_COMMENT_ANCHOR + "\n\n## SentinelQA — quality 87 (pass_with_warnings)\n"
    return str(body)


# ---------------------------------------------------------------------------
# GitHub poster
# ---------------------------------------------------------------------------


def test_github_first_run_creates_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No existing comment → POST a new one."""

    fake, calls = _make_github_client(
        monkeypatch,
        responses=[
            [],  # GET /comments → []
            {"id": 42, "html_url": "https://github.com/owner/repo/issues/1#c42"},
        ],
    )
    result = GH_POSTER.upsert_comment(
        repo="owner/repo", pr_number=1, body=_comment_body(), client=fake
    )
    assert result["id"] == 42
    assert len(calls) == 2
    assert calls[0].method == "GET"
    assert calls[1].method == "POST"
    assert calls[1].body == {"body": _comment_body()}


def test_github_second_run_edits_same_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing comment with anchor → PATCH that one."""

    existing = {"id": 7, "body": GH_POSTER.PR_COMMENT_ANCHOR + "\nold content"}
    fake, calls = _make_github_client(
        monkeypatch,
        responses=[
            [{"id": 1, "body": "other comment"}, existing],
            {"id": 7, "html_url": "https://github.com/owner/repo/issues/1#c7"},
        ],
    )
    result = GH_POSTER.upsert_comment(
        repo="owner/repo", pr_number=1, body=_comment_body(), client=fake
    )
    assert result["id"] == 7
    assert calls[1].method == "PATCH"
    assert calls[1].url.endswith("/comments/7")


def test_github_requires_anchor_in_body(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, calls = _make_github_client(monkeypatch, responses=[[]])
    with pytest.raises(GH_POSTER.PosterError, match="anchor"):
        GH_POSTER.upsert_comment(repo="o/r", pr_number=1, body="no anchor", client=fake)
    # Must not have called the API.
    assert calls == []


def test_github_retries_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 retries once and then succeeds — no sleep in tests."""

    import urllib.error

    monkeypatch.setattr(GH_POSTER.time, "sleep", lambda _s: None)
    err = urllib.error.HTTPError(
        url="https://api.github.com/x", code=429, msg="rate", hdrs=None, fp=None
    )
    fake, calls = _make_github_client(
        monkeypatch,
        responses=[
            err,  # GET fails first attempt
            [],  # GET succeeds — no existing
            {"id": 9, "html_url": "https://example.invalid"},
        ],
    )
    result = GH_POSTER.upsert_comment(repo="o/r", pr_number=1, body=_comment_body(), client=fake)
    assert result["id"] == 9
    assert [c.method for c in calls] == ["GET", "GET", "POST"]


def test_github_raises_on_persistent_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    monkeypatch.setattr(GH_POSTER.time, "sleep", lambda _s: None)
    err = urllib.error.HTTPError(
        url="https://api.github.com/x", code=500, msg="boom", hdrs=None, fp=None
    )
    fake, _calls = _make_github_client(monkeypatch, responses=[err])
    with pytest.raises(GH_POSTER.PosterError, match="HTTP 500"):
        GH_POSTER.upsert_comment(repo="o/r", pr_number=1, body=_comment_body(), client=fake)


def test_github_urlerror_retry_then_succeed(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    monkeypatch.setattr(GH_POSTER.time, "sleep", lambda _s: None)
    err = urllib.error.URLError("transient")
    fake, _calls = _make_github_client(
        monkeypatch,
        responses=[err, [], {"id": 11}],
    )
    result = GH_POSTER.upsert_comment(repo="o/r", pr_number=1, body=_comment_body(), client=fake)
    assert result["id"] == 11


def test_github_redact_url_strips_query() -> None:
    assert (
        GH_POSTER._redact_url("https://api.github.com/x?token=secret")
        == "https://api.github.com/x?<redacted>"
    )
    assert GH_POSTER._redact_url("https://api.github.com/x") == "https://api.github.com/x"


def test_github_persistent_urlerror_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    monkeypatch.setattr(GH_POSTER.time, "sleep", lambda _s: None)
    err = urllib.error.URLError("dead")
    fake, _calls = _make_github_client(monkeypatch, responses=[err, err, err])
    with pytest.raises(GH_POSTER.PosterError):
        GH_POSTER.upsert_comment(repo="o/r", pr_number=1, body=_comment_body(), client=fake)


def test_github_main_resolves_token_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = _comment_body()
    report = tmp_path / "report.md"
    report.write_text(body, encoding="utf-8")

    captured: dict[str, Any] = {}

    def _fake_upsert(
        *,
        repo: str,
        pr_number: int,
        body: str,
        client: Any,
    ) -> dict[str, Any]:
        captured["repo"] = repo
        captured["pr"] = pr_number
        captured["body"] = body
        captured["token"] = client._token
        return {"id": 1, "html_url": "https://example.invalid"}

    monkeypatch.setattr(GH_POSTER, "upsert_comment", _fake_upsert)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_supersecret_value")

    exit_code = GH_POSTER.main(["--report-markdown", str(report), "--repo", "o/r", "--pr", "1"])
    assert exit_code == 0
    assert captured["repo"] == "o/r"
    assert captured["pr"] == 1
    assert captured["token"] == "ghp_supersecret_value"


def test_github_main_refuses_empty_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = _comment_body()
    report = tmp_path / "report.md"
    report.write_text(body, encoding="utf-8")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    exit_code = GH_POSTER.main(["--report-markdown", str(report), "--repo", "o/r", "--pr", "1"])
    assert exit_code == 1


def test_github_main_refuses_missing_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_x")
    exit_code = GH_POSTER.main(
        ["--report-markdown", str(tmp_path / "missing.md"), "--repo", "o/r", "--pr", "1"]
    )
    assert exit_code == 1


def test_github_main_refuses_unanchored_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "no-anchor.md"
    report.write_text("# Hello\nno anchor here", encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_x")
    exit_code = GH_POSTER.main(["--report-markdown", str(report), "--repo", "o/r", "--pr", "1"])
    assert exit_code == 1


def test_github_log_records_never_carry_token(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    import urllib.error

    monkeypatch.setattr(GH_POSTER.time, "sleep", lambda _s: None)
    err = urllib.error.HTTPError(
        url="https://api.github.com/x?token=ghp_LEAKYTOKEN",
        code=429,
        msg="rate",
        hdrs=None,
        fp=None,
    )
    fake, _calls = _make_github_client(monkeypatch, responses=[err, [], {"id": 9}])
    with caplog.at_level(logging.WARNING):
        GH_POSTER.upsert_comment(repo="o/r", pr_number=1, body=_comment_body(), client=fake)
    rendered = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "ghp_LEAKYTOKEN" not in rendered
    assert "ghp_fake_test_token" not in rendered


# ---------------------------------------------------------------------------
# GitLab poster
# ---------------------------------------------------------------------------


def _gl_comment_body() -> str:
    return str(GL_POSTER.PR_COMMENT_ANCHOR + "\n\n## SentinelQA summary\n")


def test_gitlab_first_run_creates_note(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, calls = _make_gitlab_client(
        monkeypatch,
        responses=[
            [],
            {"id": 100},
        ],
    )
    result = GL_POSTER.upsert_note(
        api_url="https://gitlab.example/api/v4",
        project_id="42",
        mr_iid=7,
        body=_gl_comment_body(),
        client=fake,
    )
    assert result["id"] == 100
    assert calls[1].method == "POST"
    assert "/projects/42/merge_requests/7/notes" in calls[1].url


def test_gitlab_second_run_edits_same_note(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = {"id": 55, "body": GL_POSTER.PR_COMMENT_ANCHOR + "\nold"}
    fake, calls = _make_gitlab_client(
        monkeypatch,
        responses=[
            [{"id": 9, "body": "other"}, existing],
            {"id": 55},
        ],
    )
    GL_POSTER.upsert_note(
        api_url="https://gitlab.example/api/v4/",
        project_id="42",
        mr_iid=7,
        body=_gl_comment_body(),
        client=fake,
    )
    assert calls[1].method == "PUT"
    assert calls[1].url.endswith("/notes/55")


def test_gitlab_main_resolves_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = tmp_path / "report.md"
    report.write_text(_gl_comment_body(), encoding="utf-8")

    captured: dict[str, Any] = {}

    def _fake_upsert(
        *,
        api_url: str,
        project_id: str,
        mr_iid: int,
        body: str,
        client: Any,
    ) -> dict[str, Any]:
        captured["api_url"] = api_url
        captured["project_id"] = project_id
        captured["mr_iid"] = mr_iid
        captured["token"] = client._token
        return {"id": 7}

    monkeypatch.setattr(GL_POSTER, "upsert_note", _fake_upsert)
    monkeypatch.setenv("SENTINELQA_GITLAB_TOKEN", "glpat_xxxxx")

    exit_code = GL_POSTER.main(
        [
            "--report-markdown",
            str(report),
            "--api-url",
            "https://gitlab.example/api/v4",
            "--project-id",
            "42",
            "--mr",
            "7",
        ]
    )
    assert exit_code == 0
    assert captured["api_url"] == "https://gitlab.example/api/v4"
    assert captured["project_id"] == "42"
    assert captured["mr_iid"] == 7
    assert captured["token"] == "glpat_xxxxx"


def test_gitlab_main_refuses_empty_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = tmp_path / "report.md"
    report.write_text(_gl_comment_body(), encoding="utf-8")
    monkeypatch.delenv("SENTINELQA_GITLAB_TOKEN", raising=False)
    exit_code = GL_POSTER.main(
        [
            "--report-markdown",
            str(report),
            "--api-url",
            "https://gitlab.example/api/v4",
            "--project-id",
            "42",
            "--mr",
            "7",
        ]
    )
    assert exit_code == 1


def test_gitlab_main_refuses_missing_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SENTINELQA_GITLAB_TOKEN", "glpat_x")
    code = GL_POSTER.main(
        [
            "--report-markdown",
            str(tmp_path / "missing.md"),
            "--api-url",
            "https://gitlab.example/api/v4",
            "--project-id",
            "42",
            "--mr",
            "7",
        ]
    )
    assert code == 1


def test_gitlab_main_refuses_unanchored_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "no-anchor.md"
    report.write_text("# No anchor\n", encoding="utf-8")
    monkeypatch.setenv("SENTINELQA_GITLAB_TOKEN", "glpat_x")
    code = GL_POSTER.main(
        [
            "--report-markdown",
            str(report),
            "--api-url",
            "https://gitlab.example/api/v4",
            "--project-id",
            "42",
            "--mr",
            "7",
        ]
    )
    assert code == 1


def test_gitlab_upsert_refuses_unanchored_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake, _calls = _make_gitlab_client(monkeypatch, responses=[])
    with pytest.raises(GL_POSTER.PosterError, match="anchor"):
        GL_POSTER.upsert_note(
            api_url="https://gitlab.example/api/v4",
            project_id="42",
            mr_iid=7,
            body="no anchor",
            client=fake,
        )


def test_gitlab_urlerror_retry_then_succeed(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    monkeypatch.setattr(GL_POSTER.time, "sleep", lambda _s: None)
    err = urllib.error.URLError("connection reset")
    fake, _calls = _make_gitlab_client(
        monkeypatch,
        responses=[err, [], {"id": 1}],
    )
    result = GL_POSTER.upsert_note(
        api_url="https://gitlab.example/api/v4",
        project_id="42",
        mr_iid=7,
        body=_gl_comment_body(),
        client=fake,
    )
    assert result["id"] == 1


def test_gitlab_persistent_http_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    monkeypatch.setattr(GL_POSTER.time, "sleep", lambda _s: None)
    err = urllib.error.HTTPError(
        url="https://gitlab.example/api/v4/x",
        code=403,
        msg="forbidden",
        hdrs=None,
        fp=None,
    )
    fake, _calls = _make_gitlab_client(monkeypatch, responses=[err])
    with pytest.raises(GL_POSTER.PosterError, match="HTTP 403"):
        GL_POSTER.upsert_note(
            api_url="https://gitlab.example/api/v4",
            project_id="42",
            mr_iid=7,
            body=_gl_comment_body(),
            client=fake,
        )


def test_gitlab_redact_url_strips_query() -> None:
    assert GL_POSTER._redact_url("https://gitlab.example/api/v4/x?token=secret") == (
        "https://gitlab.example/api/v4/x?<redacted>"
    )
    assert GL_POSTER._redact_url("https://gitlab.example/api/v4/x") == (
        "https://gitlab.example/api/v4/x"
    )


def test_gitlab_retry_on_500(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    monkeypatch.setattr(GL_POSTER.time, "sleep", lambda _s: None)
    err = urllib.error.HTTPError(
        url="https://gitlab.example/api/v4/x",
        code=500,
        msg="boom",
        hdrs=None,
        fp=None,
    )
    fake, calls = _make_gitlab_client(monkeypatch, responses=[err, [], {"id": 1}])
    result = GL_POSTER.upsert_note(
        api_url="https://gitlab.example/api/v4",
        project_id="42",
        mr_iid=7,
        body=_gl_comment_body(),
        client=fake,
    )
    assert result["id"] == 1
    assert [c.method for c in calls] == ["GET", "GET", "POST"]
