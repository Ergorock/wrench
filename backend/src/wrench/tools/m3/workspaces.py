"""Workspaces et insights Ming.le : liste, export en mémoire, recensement des widgets.

Authentification : en-tête `x-infor-authorization: Bearer <jeton de session portail>` (jeton
`TENANT~…`, ~1 h), capturé dans Edge ou collé à la main.
"""

import csv
import io
import json
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel

from wrench.sdk import ToolError
from wrench.tools.m3.http import call, json_of
from wrench.tools.m3.session import PORTAL_HOST, RequestMatcher, Session, check_tenant

TOKEN_HEADER = "x-infor-authorization"
SUBTYPES = {"workspaces": [0, 2], "insights": [1]}
_LOCALE = {"language": "fr-FR", "locale": "fr-FR", "timeZone": "Europe/Berlin"}

# (id widget, titre widget, id workspace, titre workspace)
Occurrence = tuple[str, str, str, str]


class Workspace(BaseModel):
    id: str
    title: str
    owner: str
    changed: str


class WidgetRow(BaseModel):
    widget_id: str
    label: str
    workspace_title: str
    workspace_id: str
    count: int


class WidgetTotal(BaseModel):
    widget_id: str
    label: str
    count: int


def portal_url(tenant: str) -> str:
    return f"{PORTAL_HOST}/{check_tenant(tenant)}/"


def matcher() -> RequestMatcher:
    return RequestMatcher("mingle-portal", TOKEN_HEADER)


def manual_session(token: str) -> Session:
    """Session à partir d'un jeton collé (avec ou sans le préfixe « Bearer »)."""
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[len("bearer ") :].strip()
    if not token:
        raise ToolError("token_required", "Token is required")
    return Session(PORTAL_HOST, {}, {TOKEN_HEADER: f"Bearer {token}"})


def _api(tenant: str) -> str:
    return f"/v2/admin/api/{check_tenant(tenant)}"


def list_items(
    session: Session,
    tenant: str,
    kind: str,
    query: str = "",
    http: requests.Session | None = None,
) -> list[Workspace]:
    body = {
        "paging": {"offset": 0},
        "pageSize": 100,
        "query": query,
        "sortOrder": 1,
        "sortBy": 1,
        "workspaceType": 2,
        "workspaceSubTypes": SUBTYPES[kind],
        **_LOCALE,
    }
    resp = call(
        "POST",
        session,
        f"{_api(tenant)}/workspace/list",
        referer="/",
        json_body=body,
        headers={"Content-Type": "application/json"},
        timeout=120,
        http=http,
    )
    data = json_of(resp)
    content = data.get("content", []) if isinstance(data, dict) else []
    items = []
    for entry in content:
        ws = entry.get("workspace", {}) if isinstance(entry, dict) else {}
        items.append(
            Workspace(
                id=str(ws.get("id", "")),
                title=str(ws.get("title", "")),
                owner=str(ws.get("ownerName", "")),
                changed=str(ws.get("changedTZ", "")),
            )
        )
    return items


def export_zip(
    session: Session, tenant: str, ids: list[str], http: requests.Session | None = None
) -> bytes:
    resp = call(
        "POST",
        session,
        f"{_api(tenant)}/workspace/published/export",
        referer="/",
        json_body={"content": ids, "entityCategory": 18, **_LOCALE},
        headers={"Content-Type": "application/json"},
        timeout=120,
        http=http,
    )
    kind = resp.headers.get("content-type", "")
    if "zip" not in kind and "octet-stream" not in kind:
        raise ToolError("bad_response", f"Unexpected export content-type: {kind!r}")
    return resp.content


# --- analyse ---------------------------------------------------------------------------


def _widget_nodes(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, list):
        for item in node:
            yield from _widget_nodes(item)
    elif isinstance(node, dict):
        if node.get("type") == "widget":
            yield node
        yield from _widget_nodes(node.get("nodes"))


def widgets_in_zip(zip_bytes: bytes) -> list[Occurrence]:
    found: list[Occurrence] = []
    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ToolError("bad_response", "The export is not a valid ZIP") from exc
    with archive:
        for name in archive.namelist():
            if not name.lower().endswith(".json"):
                continue
            try:
                page = json.loads(archive.read(name).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(page, dict):
                continue
            dashboard = page.get("dashboard")
            containers = dashboard.get("containers", []) if isinstance(dashboard, dict) else []
            for node in _widget_nodes(containers):
                ref = node.get("ref") or {}
                data = node.get("data") or {}
                widget_id = str(ref.get("id") or data.get("id") or "")
                if widget_id:
                    found.append(
                        (
                            widget_id,
                            str(data.get("title", "")),
                            str(page.get("id", "")),
                            str(page.get("title", "")),
                        )
                    )
    return found


def _label(titles: list[str], fallback: str) -> str:
    distinct = list(dict.fromkeys(t for t in titles if t))
    return ", ".join(distinct) if distinct else fallback


def aggregate(occurrences: list[Occurrence]) -> tuple[list[WidgetTotal], list[WidgetRow]]:
    totals: Counter[str] = Counter()
    total_titles: dict[str, list[str]] = defaultdict(list)
    per_ws: Counter[tuple[str, str, str]] = Counter()
    ws_titles: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for widget_id, title, ws_id, ws_title in occurrences:
        key = (widget_id, ws_id, ws_title)
        totals[widget_id] += 1
        per_ws[key] += 1
        total_titles[widget_id].append(title)
        ws_titles[key].append(title)
    summary = sorted(
        (
            WidgetTotal(widget_id=w, label=_label(total_titles[w], w), count=c)
            for w, c in totals.items()
        ),
        key=lambda s: (-s.count, s.widget_id),
    )
    rows = sorted(
        (
            WidgetRow(
                widget_id=k[0],
                label=_label(ws_titles[k], k[0]),
                workspace_id=k[1],
                workspace_title=k[2],
                count=c,
            )
            for k, c in per_ws.items()
        ),
        key=lambda r: (r.workspace_title, -r.count, r.widget_id),
    )
    return summary, rows


def write_csv(path: Path, rows: list[WidgetRow]) -> None:
    """CSV `;`, utf-8-sig (ouverture directe dans Excel)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Identifiant", "Libellé", "Workspace", "Id workspace", "Occurrences"])
        for r in rows:
            writer.writerow([r.widget_id, r.label, r.workspace_title, r.workspace_id, r.count])
