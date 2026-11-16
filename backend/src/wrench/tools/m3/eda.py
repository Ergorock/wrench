"""Export EDA : /mnerest/ux/runtime/get pour chaque EDA, un fichier JSON par EDA."""

import re
from pathlib import Path

import requests

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
