"""Session M3 / Infor OS capturée dans Edge (piloté par Playwright).

L'utilisateur se connecte lui-même (SSO, MFA compris) dans la fenêtre Edge. On observe les
requêtes de la page : la première qui correspond à `RequestMatcher` donne l'URL de base et un
en-tête (jeton CSRF ou Bearer), puis on lit les cookies de cet hôte et on ferme Edge. Aucun mot
de passe n'est lu ni stocké. Le profil Edge dédié est partagé par tous les onglets de l'outil :
il contient la session, à traiter comme un secret.
"""

import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from wrench.core.paths import app_data_dir
from wrench.sdk import ToolError

PORTAL_HOST = "https://mingle-portal.eu1.inforcloudsuite.com"
LOGIN_TIMEOUT_S = 600
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36 Edg/157.0.0.0"
)
_TENANT_RE = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class Session:
    base_url: str
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)  # CSRF ou Bearer capturé


def check_tenant(tenant: str) -> str:
    tenant = tenant.strip()
    if not tenant:
        raise ToolError("tenant_required", "Tenant is required")
    if not _TENANT_RE.fullmatch(tenant):
        raise ToolError("invalid_tenant", "Invalid tenant")
    return tenant


def profile_dir() -> Path:
    if os.environ.get("WRENCH_DATA_DIR") or not os.environ.get("LOCALAPPDATA"):
        return app_data_dir() / "m3-edge-profile"
    return Path(os.environ["LOCALAPPDATA"]) / "Wrench" / "m3-edge-profile"


class RequestMatcher:
    """Retient la requête la plus récente dont l'URL contient `marker` et qui porte `header`
    (si `header` est vide, l'URL seule suffit). `header` est en minuscules."""

    def __init__(self, marker: str, header: str = "") -> None:
        self.marker = marker
        self.header = header
        self.base_url = ""
        self.api_url = ""
        self.headers: dict[str, str] = {}

    def feed(self, url: str, headers: dict[str, str]) -> None:
        if self.marker not in url:
            return
        value = ""
        if self.header:
            value = next((v for k, v in headers.items() if k.lower() == self.header), "")
            if not value:
                return
        parts = urlsplit(url)
        self.base_url = f"{parts.scheme}://{parts.netloc}"
        self.api_url = url
        if self.header:
            self.headers = {self.header: value}

    @property
    def ready(self) -> bool:
        return bool(self.base_url)


def capture_session(
    portal_url: str,
    matcher: RequestMatcher,
    *,
    on_status: Callable[[str], None],
    should_cancel: Callable[[], bool],
    timeout_s: int = LOGIN_TIMEOUT_S,
) -> Session:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    profile = profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as pw:
            try:
                context = pw.chromium.launch_persistent_context(
                    str(profile), channel="msedge", headless=False
                )
            except PlaywrightError as exc:
                raise ToolError(
                    "edge_launch_failed", f"Cannot start Edge: {str(exc).splitlines()[0]}"
                ) from exc
            try:
                context.on("request", lambda req: matcher.feed(req.url, req.headers))
                page = context.pages[0] if context.pages else context.new_page()
                on_status("edge_opened")
                page.goto(portal_url, wait_until="commit", timeout=60_000)
                deadline = time.monotonic() + timeout_s
                while not matcher.ready:
                    if should_cancel():
                        raise ToolError("login_cancelled", "Login cancelled")
                    if time.monotonic() > deadline:
                        raise ToolError("login_timeout", "No M3 request seen")
                    page.wait_for_timeout(300)
                page.wait_for_timeout(1000)  # laisse les cookies se stabiliser
                cookies = {
                    c["name"]: c["value"]
                    for c in context.cookies([matcher.api_url])
                    if "name" in c and "value" in c
                }
            finally:
                context.close()
    except PlaywrightError as exc:
        raise ToolError("edge_closed", f"Edge closed or Playwright error: {exc}") from exc
    if not cookies and not matcher.headers:
        raise ToolError("no_session", "No session cookie read")
    return Session(matcher.base_url, cookies, dict(matcher.headers))
