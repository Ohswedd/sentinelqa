"""Auth boundary detection (task 05.05).

Runs two HTTP passes against the same crawl scope:

1. **Anonymous** — no cookies, no credentials.
2. **Authenticated** — POST credentials to ``auth.login_url``, persist
   cookies, then re-crawl.

The diff produces an :class:`AuthBoundaryReport` listing which routes are
auth-required, which redirect to login, which have a UI-only auth smell
(visible to anonymous but the UI implies otherwise), and which look like
admin-only routes that returned 200 to a non-admin user.

Safety: credentials are never persisted in artifacts — only the env-var
names are recorded. The login POST body is also never written to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from engine.discovery.crawler import (
    Crawler,
    CrawlPage,
    CrawlPolicy,
    CrawlResult,
)
from engine.domain.discovery_graph import AuthBoundary
from engine.domain.ids import validate_id


@dataclass(frozen=True)
class AuthCredentials:
    """The credential surface the boundary detector consumes.

    ``username`` / ``password`` are the *resolved* values pulled from env
    vars by the caller — this class never resolves them itself, so tests
    can pass literal strings without monkeypatching ``os.environ``. The
    env-var *names* are recorded separately for the audit log.
    """

    login_url: str
    username_env_name: str
    password_env_name: str
    username: str
    password: str
    username_field: str = "username"
    password_field: str = "password"


@dataclass(frozen=True)
class AuthRouteVerdict:
    """Per-route boundary classification."""

    url: str
    requires_auth: bool
    redirects_to: str | None
    anon_status: int
    auth_status: int | None
    ui_only_auth: bool
    role_escalation_hint: bool


@dataclass(frozen=True)
class AuthBoundaryReport:
    """Aggregate output that gets persisted to ``auth.json``."""

    verdicts: tuple[AuthRouteVerdict, ...] = field(default_factory=tuple)
    boundaries: tuple[AuthBoundary, ...] = field(default_factory=tuple)
    login_succeeded: bool = False
    login_url: str | None = None
    username_env_name: str | None = None
    password_env_name: str | None = None


class AuthBoundaryDetector:
    """Two-pass anonymous/authenticated crawl + diff."""

    def __init__(self, crawler: Crawler | None = None) -> None:
        self._crawler = crawler or Crawler()

    def detect(
        self,
        *,
        base_url: str,
        run_id: str,
        policy: CrawlPolicy,
        anonymous_crawl: CrawlResult,
        credentials: AuthCredentials | None,
        route_id_by_url: dict[str, str],
    ) -> AuthBoundaryReport:
        # Without credentials, we can still mark routes that redirect to a
        # login page or return 401/403 as auth-required.
        if credentials is None:
            verdicts = self._verdicts_from_anonymous(anonymous_crawl)
            boundaries = self._build_boundaries(verdicts, route_id_by_url)
            return AuthBoundaryReport(
                verdicts=tuple(verdicts),
                boundaries=tuple(boundaries),
                login_succeeded=False,
                login_url=None,
                username_env_name=None,
                password_env_name=None,
            )

        with httpx.Client(
            timeout=policy.request_timeout_seconds,
            follow_redirects=True,
        ) as client:
            login_succeeded = self._perform_login(client, credentials)
            if not login_succeeded:
                # Even with bad credentials, we still report the anonymous-only verdicts.
                verdicts = self._verdicts_from_anonymous(anonymous_crawl)
                boundaries = self._build_boundaries(verdicts, route_id_by_url)
                return AuthBoundaryReport(
                    verdicts=tuple(verdicts),
                    boundaries=tuple(boundaries),
                    login_succeeded=False,
                    login_url=credentials.login_url,
                    username_env_name=credentials.username_env_name,
                    password_env_name=credentials.password_env_name,
                )

            cookies = dict(client.cookies)
            authenticated_crawl = self._crawler.crawl(
                base_url,
                run_id=run_id,
                policy=policy,
                extra_cookies=cookies,
            )

        verdicts = self._verdicts_from_pair(
            anonymous_crawl=anonymous_crawl,
            authenticated_crawl=authenticated_crawl,
        )
        boundaries = self._build_boundaries(verdicts, route_id_by_url)
        return AuthBoundaryReport(
            verdicts=tuple(verdicts),
            boundaries=tuple(boundaries),
            login_succeeded=True,
            login_url=credentials.login_url,
            username_env_name=credentials.username_env_name,
            password_env_name=credentials.password_env_name,
        )

    def _perform_login(self, client: httpx.Client, credentials: AuthCredentials) -> bool:
        payload = {
            credentials.username_field: credentials.username,
            credentials.password_field: credentials.password,
        }
        try:
            response = client.post(credentials.login_url, data=payload)
        except httpx.HTTPError:
            return False
        # Strict criteria: 2xx OR a 3xx redirect that lands on a non-login URL.
        if 200 <= response.status_code < 300:
            return True
        if 300 <= response.status_code < 400:
            return "login" not in response.headers.get("location", "").lower()
        return False

    def _verdicts_from_anonymous(self, crawl: CrawlResult) -> list[AuthRouteVerdict]:
        out: list[AuthRouteVerdict] = []
        for page in crawl.pages:
            requires_auth, redirects_to = self._classify_anonymous(page)
            out.append(
                AuthRouteVerdict(
                    url=page.url,
                    requires_auth=requires_auth,
                    redirects_to=redirects_to,
                    anon_status=page.status_code,
                    auth_status=None,
                    ui_only_auth=False,
                    role_escalation_hint=False,
                )
            )
        return out

    def _classify_anonymous(self, page: CrawlPage) -> tuple[bool, str | None]:
        if page.status_code in (401, 403):
            return True, None
        # Soft-redirect to a login URL is the canonical "auth boundary" signal.
        lower_url = page.url.lower()
        if any(token in lower_url for token in ("/login", "/signin", "/sign-in")):
            return False, None  # The login page itself is anon-accessible.
        html_lower = page.html.lower()
        if 'name="password"' in html_lower or 'type="password"' in html_lower:
            return True, page.url
        return False, None

    def _verdicts_from_pair(
        self,
        *,
        anonymous_crawl: CrawlResult,
        authenticated_crawl: CrawlResult,
    ) -> list[AuthRouteVerdict]:
        by_anon: dict[str, CrawlPage] = {p.url: p for p in anonymous_crawl.pages}
        by_auth: dict[str, CrawlPage] = {p.url: p for p in authenticated_crawl.pages}
        out: list[AuthRouteVerdict] = []
        for url in sorted(set(by_anon) | set(by_auth)):
            anon = by_anon.get(url)
            auth = by_auth.get(url)
            anon_status = anon.status_code if anon else 0
            auth_status = auth.status_code if auth else None
            requires_auth = False
            redirects_to: str | None = None
            ui_only = False
            escalation = False

            if anon is not None:
                requires_auth, redirects_to = self._classify_anonymous(anon)
            # If anonymous got blocked (401/403/redirect) and authenticated
            # got 200, the route is firmly behind the boundary.
            if anon is not None and auth is not None:
                if (anon_status in (401, 403)) and 200 <= auth.status_code < 300:
                    requires_auth = True
                # UI-only auth: anonymous saw the page (200) but the UI markers
                # imply it should require auth (password fields present), AND
                # the authenticated pass also got 200 — this is the smell.
                if 200 <= anon_status < 300:
                    html_lower = anon.html.lower()
                    auth_lower = auth.html.lower()
                    is_admin_route = "/admin" in url.lower() or "admin" in html_lower
                    if is_admin_route and 200 <= auth.status_code < 300 and "admin" in url.lower():
                        # Anonymous got into an admin route — that's an escalation hint.
                        escalation = True
                    if (
                        not requires_auth
                        and 200 <= anon_status < 300
                        and "logged" in auth_lower
                        and "logged" not in html_lower
                    ):
                        ui_only = True

            out.append(
                AuthRouteVerdict(
                    url=url,
                    requires_auth=requires_auth,
                    redirects_to=redirects_to,
                    anon_status=anon_status,
                    auth_status=auth_status,
                    ui_only_auth=ui_only,
                    role_escalation_hint=escalation,
                )
            )
        return out

    def _build_boundaries(
        self,
        verdicts: list[AuthRouteVerdict],
        route_id_by_url: dict[str, str],
    ) -> list[AuthBoundary]:
        out: list[AuthBoundary] = []
        seen_routes: set[str] = set()
        for verdict in verdicts:
            if not verdict.requires_auth:
                continue
            route_id = route_id_by_url.get(verdict.url)
            if route_id is None or route_id in seen_routes:
                continue
            try:
                validate_id(route_id, prefix="RT")
            except ValueError:
                continue
            seen_routes.add(route_id)
            try:
                out.append(
                    AuthBoundary(
                        route_id=route_id,
                        required_role=None,
                        enforced_server_side=not verdict.ui_only_auth,
                    )
                )
            except ValidationError:
                continue
        return out


def is_same_host(url_a: str, url_b: str) -> bool:
    return urlparse(url_a).netloc == urlparse(url_b).netloc


__all__ = [
    "AuthBoundaryDetector",
    "AuthBoundaryReport",
    "AuthCredentials",
    "AuthRouteVerdict",
    "is_same_host",
]
