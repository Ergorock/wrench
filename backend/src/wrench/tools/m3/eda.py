"""Export EDA : /mnerest/ux/runtime/get pour chaque EDA, un fichier JSON par EDA."""

import re
from pathlib import Path

import requests
from pydantic import BaseModel

from wrench.sdk import ToolError
from wrench.tools.m3.http import call, json_of
from wrench.tools.m3.session import RequestMatcher, Session

CSRF_HEADER = "mua_csrf_token"
PORTAL_PATH = "/mne/ext/h5xi/?LogicalId=lid:%2F%2Finfor.m3.m3&inforCurrentLanguage=fr-FR&LNC=FR"
DEFAULT_BASE_URL = "https://m3prdeuc1b.m3.eu1.inforcloudsuite.com"


def portal_url(base_url: str) -> str:
    return base_url.strip().rstrip("/") + PORTAL_PATH


def matcher() -> RequestMatcher:
    return RequestMatcher("/mnerest/", CSRF_HEADER)


def parse_edas(text: str) -> list[str]:
    """Un EDA par ligne (ou 1re colonne d'un collage Excel/CSV) ; vides, en-tête et doublons
    ignorés."""
    values = []
    for line in text.splitlines():
        first = re.split(r"[;\t,]", line, maxsplit=1)[0].strip()
        if first:
            values.append(first)
    if values and values[0].lower() in ("eda", "{eda}", "shortid"):
        values = values[1:]
    return list(dict.fromkeys(values))


PAGE_SIZE = 50
MAX_PAGES = 100
_ID_KEYS = ("shortId", "short_id", "id", "name")


class EdaItem(BaseModel):
    id: str
    fields: dict[str, str]  # champs simples de l'entrée, tels que renvoyés par le serveur


def parse_list(payload: object) -> list[EdaItem]:
    """Entrées de `/mnerest/ux/dev/list` : la liste est sous `content` (ou la première liste de
    la réponse) ; `id` est le premier champ connu parmi shortId, id, name."""
    entries: object = None
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = payload.get("content")
        if not isinstance(entries, list):
            entries = next((v for v in payload.values() if isinstance(v, list)), None)
    if not isinstance(entries, list):
        raise ToolError("bad_response", "Unexpected EDA list response")
    items = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        fields = {k: str(v) for k, v in entry.items() if isinstance(v, str | int | float | bool)}
        ident = next((fields[k] for k in _ID_KEYS if fields.get(k)), "")
        if ident:
            items.append(EdaItem(id=ident, fields=fields))
    return items


def list_edas(session: Session, http: requests.Session | None = None) -> list[EdaItem]:
    items: list[EdaItem] = []
    for page in range(MAX_PAGES):
        resp = call(
            "POST",
            session,
            "/mnerest/ux/dev/list",
            referer="/mne/ext/h5xi/",
            json_body={
                "paging": {"offset": page * PAGE_SIZE, "isEnd": False},
                "sortBy": 4,
                "sortOrder": 2,
                "filters": [{"filterType": 0}],
                "pageSize": PAGE_SIZE,
                "query": "",
            },
            headers={"Content-Type": "application/json"},
            http=http,
        )
        payload = json_of(resp)
        batch = parse_list(payload)
        items.extend(batch)
        paging = payload.get("paging") if isinstance(payload, dict) else None
        is_end = isinstance(paging, dict) and paging.get("isEnd") is True
        if is_end or len(batch) < PAGE_SIZE:
            break
    return list(dict((i.id, i) for i in items).values())


def fetch_eda(
    session: Session,
    eda: str,
    company: str,
    division: str,
    language: str,
    http: requests.Session | None = None,
) -> object:
    resp = call(
        "POST",
        session,
        "/mnerest/ux/runtime/get",
        referer="/mne/ext/h5xi/",
        json_body={
            "application": {"shortId": eda},
            "company": company,
            "division": division,
            "language": language,
        },
        headers={"Content-Type": "application/json"},
        http=http,
    )
    return json_of(resp)


def safe_name(name: str) -> str:
    return re.sub(r'[\/:*?"<>|]', "_", name)


def file_for(out_dir: Path, eda: str) -> Path:
    return out_dir / f"{safe_name(eda)}.json"
