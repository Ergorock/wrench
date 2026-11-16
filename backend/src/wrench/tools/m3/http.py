"""Appel HTTP commun aux quatre onglets : 401/403 = session expirée."""

from typing import Any

import requests

from wrench.sdk import ToolError
from wrench.tools.m3.session import USER_AGENT, Session


def call(
    method: str,
    session: Session,
    path: str,
    *,
    referer: str,
    json_body: Any = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
    http: requests.Session | None = None,
) -> requests.Response:
    merged = {
        "Accept": "application/json, text/plain, */*",
        "Origin": session.base_url,
        "Referer": session.base_url + referer,
        "User-Agent": USER_AGENT,
        **session.headers,
        **(headers or {}),
    }
    try:
        resp = (http or requests).request(
            method,
            session.base_url + path,
            json=json_body,
            headers=merged,
            cookies=session.cookies,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise ToolError("network_error", f"Network error: {exc}") from exc
    if resp.status_code in (401, 403):
        raise ToolError("session_expired", f"HTTP {resp.status_code}")
    if not resp.ok:
        raise ToolError("http_error", f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp


def json_of(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except ValueError as exc:  # page de connexion HTML : la session est morte
        raise ToolError("session_expired", "Response is not JSON") from exc
