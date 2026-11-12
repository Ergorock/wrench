"""Remote URL helpers (pure functions): hosting kind and web address."""

import re
from typing import Literal
from urllib.parse import urlsplit

HostKind = Literal["github", "gitea", "other", "none"]

# scp-like syntax `[user@]host:path`; a one-letter "host" is a Windows drive (C:/repos).
_SCP = re.compile(r"^(?:(?P<user>[^@/\\\s]+)@)?(?P<host>[^@/\\:\s]{2,}):(?!//)(?P<path>.+)$")


def _normalize(url: str) -> str:
    match = _SCP.match(url)
    if match and "://" not in url:
        user = f"{match['user']}@" if match["user"] else ""
        return f"ssh://{user}{match['host']}/{match['path'].lstrip('/')}"
    return url


def _host(url: str) -> str | None:
    parts = urlsplit(_normalize(url))
    if parts.scheme in ("http", "https", "ssh", "git") and parts.hostname:
        return parts.hostname
    return None


def host_kind(url: str | None) -> HostKind:
    if not url or not url.strip():
        return "none"
    host = _host(url.strip())
    if host == "github.com":
        return "github"
    if host and "gitea" in host:
        return "gitea"
    return "other"


def web_url(url: str | None) -> str | None:
    if not url or not url.strip():
        return None
    try:
        parts = urlsplit(_normalize(url.strip()))
        host = _host(url.strip())
        port = parts.port
    except ValueError:
        return None
    path = parts.path.strip("/").removesuffix(".git").strip("/")
    if host is None or not path:
        return None
    if parts.scheme in ("http", "https"):
        netloc = f"{host}:{port}" if port else host
        return f"{parts.scheme}://{netloc}/{path}"
    return f"https://{host}/{path}"
