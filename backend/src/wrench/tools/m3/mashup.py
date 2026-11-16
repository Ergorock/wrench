"""Liste des apps (mashups) : API interne de H5 Administration (mnerest)."""

import secrets
import string

import requests
from pydantic import BaseModel

from wrench.sdk import ToolError
from wrench.tools.m3.http import call, json_of
from wrench.tools.m3.session import PORTAL_HOST, RequestMatcher, Session, check_tenant

_ID_ALPHABET = string.ascii_uppercase + string.digits
MARKER = "/mnerest/"


class Mashup(BaseModel):
    name: str
    description: str
    category: int
    visibility: int
    created_by: str
    changed_by: str
    change_date: str


def portal_url(tenant: str) -> str:
    return (
        f"{PORTAL_HOST}/v2/{check_tenant(tenant)}/c7e3a053-6577-4707-92d0-cbc08e48f914"
        "?favoriteContext=%3FLogicalId%3Dlid%3A%2F%2Finfor.m3.m3%26program%3D"
        "%2Fmne%2Fguava%2Fadmin%2F%26name%3DH5%20Administration"
        "&LogicalId=lid%3A%2F%2Finfor.m3.m3"
    )


def matcher() -> RequestMatcher:
    return RequestMatcher(MARKER)


def parse_apps(payload: object) -> list[Mashup]:
    try:
        apps = payload["content"]["apps"]  # type: ignore[index]
        if not isinstance(apps, list):
            raise TypeError("apps is not a list")
        return [
            Mashup(
                name=str(a["name"]),
                description=str(a.get("description") or ""),
                category=int(a["category"]),
                visibility=int(a["visibility"]),
                created_by=str(a.get("createdBy") or ""),
                changed_by=str(a.get("changedBy") or ""),
                change_date=str(a.get("changeDate") or ""),
            )
            for a in apps
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolError("bad_response", f"Unexpected response: {exc}") from exc


def list_apps(session: Session, http: requests.Session | None = None) -> list[Mashup]:
    body = {
        "content": "",
        "parameters": None,
        "id": "".join(secrets.choice(_ID_ALPHABET) for _ in range(16)),
        "resource": "admin",
        "name": "get",
    }
    resp = call(
        "POST",
        session,
        "/mnerest/service/",
        referer="/mne/guava/admin/",
        json_body=body,
        headers={
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30,
        http=http,
    )
    return parse_apps(json_of(resp))
