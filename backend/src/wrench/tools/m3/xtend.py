"""Code Groovy XtendM3 : liste des programmes, récupération locale, recherche hors ligne.

Endpoints foundation-rest (cookies + en-tête fnd-csrf-token). Le code est dans le champ `code`
(base64 UTF-8) de la réponse. Dossier local : un `<programme>_<kind>_<nom>.groovy` par source et
un `manifest.json` d'index.
"""

import base64
import binascii
import json
import re
from pathlib import Path

import requests
from pydantic import BaseModel

from wrench.sdk import ToolError
from wrench.tools.m3.http import call, json_of
from wrench.tools.m3.session import PORTAL_HOST, RequestMatcher, Session, check_tenant

CSRF_HEADER = "fnd-csrf-token"
API = "/foundation-rest/tenant/extensibility"
KINDS = ("batch", "transaction")
_SECTIONS = {"batches": "batch", "transactions": "transaction"}
_COMPONENT = {"batch": "batch/component", "transaction": "transaction/component"}
MANIFEST_NAME = "manifest.json"
MAX_SNIPPET = 200
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class Source(BaseModel):
    uuid: str
    program: str
    kind: str
    name: str
    description: str
    modified: int
    modified_by: str


class StoredSource(Source):
    file: str


class Hit(BaseModel):
    file: str
    program: str
    kind: str
    name: str
    line: int
    snippet: str


def portal_url(tenant: str) -> str:
    return (
        f"{PORTAL_HOST}/{check_tenant(tenant)}/"
        "?favoriteContext=%3FLogicalId%3Dlid%3A%2F%2Finfor.m3.m3%26program%3D"
        "%2Ffoundation-admin-ui%2F%23%2Fextensibility%26name%3DXtendM3"
        "&LogicalId=lid%3A%2F%2Finfor.m3.m3"
    )


def matcher() -> RequestMatcher:
    return RequestMatcher("/foundation-rest/", CSRF_HEADER)


# --- réseau ----------------------------------------------------------------------------


def parse_program_info(data: object) -> list[Source]:
    modules = data.get("programModules") if isinstance(data, dict) else None
    if not isinstance(modules, dict):
        return []
    refs: list[Source] = []
    for key, module in modules.items():
        if not isinstance(module, dict):
            continue
        program = str(module.get("program") or key)
        for section, kind in _SECTIONS.items():
            entries = module.get(section)
            if not isinstance(entries, dict):
                continue
            for entry_key, entry in entries.items():
                if not isinstance(entry, dict) or not entry.get("sourceUuid"):
                    continue
                modified = entry.get("modified")
                refs.append(
                    Source(
                        uuid=str(entry["sourceUuid"]),
                        program=program,
                        kind=kind,
                        name=str(entry.get("name") or entry_key),
                        description=str(entry.get("description") or ""),
                        modified=modified if isinstance(modified, int) else 0,
                        modified_by=str(entry.get("modifiedBy") or ""),
                    )
                )
    refs.sort(key=lambda r: (r.program.lower(), r.kind, r.name.lower()))
    return refs


def decode_code(data: object, uuid: str) -> str:
    """Code décodé d'une réponse `component/<uuid>` (repli : champ `code` à la racine)."""
    if not isinstance(data, dict):
        raise ToolError("bad_response", "Unexpected response")
    candidates: list[object] = []
    sources = data.get("sources")
    if isinstance(sources, dict):
        if isinstance(sources.get(uuid), dict):
            candidates.append(sources[uuid])
        candidates.extend(v for v in sources.values() if isinstance(v, dict))
    candidates.append(data)
    for entry in candidates:
        code = entry.get("code") if isinstance(entry, dict) else None
        if isinstance(code, str):
            try:
                raw = base64.b64decode("".join(code.split()), validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ToolError("bad_response", f"Invalid base64 code: {exc}") from exc
            return raw.decode("utf-8", errors="replace")
    raise ToolError("bad_response", "No code field in the response")


def list_programs(session: Session, http: requests.Session | None = None) -> list[Source]:
    resp = call("GET", session, f"{API}/program/info", referer="/foundation-admin-ui/", http=http)
    return parse_program_info(json_of(resp))


def get_code(session: Session, source: Source, http: requests.Session | None = None) -> str:
    resp = call(
        "GET",
        session,
        f"{API}/{_COMPONENT[source.kind]}/{source.uuid}",
        referer="/foundation-admin-ui/",
        http=http,
    )
    return decode_code(json_of(resp), source.uuid)


# --- dossier local ---------------------------------------------------------------------


def _safe(text: str) -> str:
    return _UNSAFE.sub("_", text).strip("._") or "x"


def file_name_for(source: Source) -> str:
    base = f"{_safe(source.program)}_{source.kind}_{_safe(source.name)}"
    if base.split("_")[0].upper() in _RESERVED:
        base = "_" + base
    return base + ".groovy"


def load_manifest(out_dir: Path) -> list[StoredSource]:
    path = out_dir / MANIFEST_NAME
    try:
        items = json.loads(path.read_text(encoding="utf-8")).get("sources", [])
        return [StoredSource.model_validate(i) for i in items]
    except (OSError, ValueError, AttributeError):
        return []


class CodeStore:
    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self._entries = {e.uuid: e for e in load_manifest(out_dir)}

    def save(self, source: Source, code: str) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        name = file_name_for(source)
        if any(e.file == name and e.uuid != source.uuid for e in self._entries.values()):
            name = f"{name[: -len('.groovy')]}_{source.uuid[:8]}.groovy"
        with open(self.out_dir / name, "w", encoding="utf-8", newline="") as fh:
            fh.write(code)
        self._entries[source.uuid] = StoredSource(**source.model_dump(), file=name)

    def flush(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        entries = sorted(
            self._entries.values(), key=lambda e: (e.program.lower(), e.kind, e.name.lower())
        )
        payload = {"sources": [e.model_dump() for e in entries]}
        (self.out_dir / MANIFEST_NAME).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def read_code(out_dir: Path, file: str) -> str:
    """Contenu d'un .groovy du dossier ; refuse tout nom qui sortirait du dossier."""
    path = (out_dir / file).resolve()
    if path.parent != out_dir.resolve() or path.suffix != ".groovy":
        raise ToolError("unknown_file", f"Unknown file: {file}")
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except OSError as exc:
        raise ToolError("unknown_file", f"Cannot read {file}") from exc


def search(
    out_dir: Path, query: str, *, regex: bool, case_sensitive: bool, kinds: set[str]
) -> list[Hit]:
    if not query:
        raise ToolError("empty_query", "Empty query")
    try:
        compiled = re.compile(query if regex else re.escape(query), 0 if case_sensitive else re.I)
    except re.error as exc:
        raise ToolError("invalid_regex", f"Invalid regex: {exc}") from exc
    hits: list[Hit] = []
    for entry in load_manifest(out_dir):
        if entry.kind not in kinds:
            continue
        try:
            code = read_code(out_dir, entry.file)
        except ToolError:
            continue  # fichier supprimé à la main
        for number, line in enumerate(code.splitlines(), start=1):
            if compiled.search(line):
                snippet = line.strip()
                if len(snippet) > MAX_SNIPPET:
                    snippet = snippet[:MAX_SNIPPET] + "…"
                hits.append(
                    Hit(
                        file=entry.file,
                        program=entry.program,
                        kind=entry.kind,
                        name=entry.name,
                        line=number,
                        snippet=snippet,
                    )
                )
    hits.sort(key=lambda h: (h.program.lower(), h.kind, h.file, h.line))
    return hits
