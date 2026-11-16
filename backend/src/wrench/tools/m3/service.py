"""Outils M3 : export des EDA, liste des mashups, workspaces et widgets, code XtendM3.

Les quatre onglets partagent un profil Edge (la connexion SSO se fait une fois) et un seul
travail de fond à la fois : connexion, export, récupération ou analyse. L'interface interroge
`get_state` tant qu'un travail tourne.
"""

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from wrench.sdk import ToolContext, ToolError, ToolService, action
from wrench.tools.m3 import eda, mashup, workspaces, xtend
from wrench.tools.m3.session import Session, capture_session, check_tenant

Target = Literal["eda", "mashup", "xtend", "workspaces"]
TARGETS: tuple[Target, ...] = ("eda", "mashup", "xtend", "workspaces")
MAX_LOG = 500


class Config(BaseModel):
    tenant: str
    eda_base_url: str
    company: str
    division: str
    language: str
    output_dir: str


class JobView(BaseModel):
    kind: str | None
    running: bool
    status: str
    done: int
    total: int
    ok: int
    failed: int
    log: list[str]
    error: dict[str, str] | None
    seq: int


class State(BaseModel):
    config: Config
    connected: dict[str, bool]
    job: JobView


class WsResult(BaseModel):
    totals: list[workspaces.WidgetTotal]
    rows: list[workspaces.WidgetRow]


@dataclass
class _Job:
    kind: str | None = None
    running: bool = False
    status: str = ""
    done: int = 0
    total: int = 0
    ok: int = 0
    failed: int = 0
    log: list[str] = field(default_factory=list)
    error: dict[str, str] | None = None
    seq: int = 0
    cancel: threading.Event = field(default_factory=threading.Event)


def default_output_dir() -> Path:
    return Path.home() / "Documents" / "Wrench M3"


class M3Service(ToolService):
    def __init__(self, ctx: ToolContext) -> None:
        super().__init__(ctx)
        self._lock = threading.Lock()
        self._job = _Job()
        self._sessions: dict[str, Session] = {}
        self._xtend_sources: dict[str, xtend.Source] = {}
        self._ws_result = WsResult(totals=[], rows=[])
        self._ws_titles: dict[str, str] = {}

    # --- configuration -------------------------------------------------------------

    def _config(self) -> Config:
        data = self.ctx.storage.load()

        def text(key: str, default: str) -> str:
            value = data.get(key)
            return value if isinstance(value, str) else default

        return Config(
            tenant=text("tenant", ""),
            eda_base_url=text("eda_base_url", eda.DEFAULT_BASE_URL),
            company=text("company", "100"),
            division=text("division", "CF0"),
            language=text("language", "FR"),
            output_dir=text("output_dir", "") or str(default_output_dir()),
        )

    def _out(self, sub: str) -> Path:
        return Path(self._config().output_dir) / sub

    # --- travail de fond -----------------------------------------------------------

    def _view(self) -> JobView:
        with self._lock:
            j = self._job
            return JobView(
                kind=j.kind, running=j.running, status=j.status, done=j.done, total=j.total,
                ok=j.ok, failed=j.failed, log=list(j.log), error=j.error, seq=j.seq,
            )  # fmt: skip

    def _update(self, job: _Job, **fields: object) -> None:
        with self._lock:
            for name, value in fields.items():
                setattr(job, name, value)

    def _log(self, job: _Job, line: str) -> None:
        with self._lock:
            job.log.append(line)
            del job.log[:-MAX_LOG]

    def _start(self, kind: str, work: Callable[[_Job], None]) -> None:
        with self._lock:
            if self._job.running:
                raise ToolError("busy", "Another operation is running")
            job = _Job(kind=kind, running=True, seq=self._job.seq + 1)
            self._job = job
        threading.Thread(target=self._run, args=(job, work), name=f"m3-{kind}", daemon=True).start()

    def _run(self, job: _Job, work: Callable[[_Job], None]) -> None:
        error: dict[str, str] | None = None
        try:
            work(job)
        except ToolError as exc:
            error = {"code": exc.code, "message": exc.message}
        except Exception as exc:
            self.ctx.logger.exception("Unexpected error in M3 job %s", job.kind)
            error = {"code": "internal_error", "message": str(exc)}
        self._update(job, running=False, error=error)

    def _expired(self, target: Target) -> None:
        self._sessions.pop(target, None)

    def _session(self, target: Target) -> Session:
        session = self._sessions.get(target)
        if session is None:
            raise ToolError("not_connected", "Not connected")
        return session

    def _guard[T](self, target: Target, fn: Callable[[Session], T]) -> T:
        """Appel synchrone : une session expirée est oubliée pour forcer la reconnexion."""
        try:
            return fn(self._session(target))
        except ToolError as exc:
            if exc.code == "session_expired":
                self._expired(target)
            raise

    # --- état et réglages ----------------------------------------------------------

    @action
    def get_state(self) -> State:
        return State(
            config=self._config(),
            connected={t: t in self._sessions for t in TARGETS},
            job=self._view(),
        )

    @action
    def set_config(
        self,
        tenant: str,
        eda_base_url: str,
        company: str,
        division: str,
        language: str,
        output_dir: str,
    ) -> Config:
        data = self.ctx.storage.load()
        data.update(
            tenant=tenant.strip(),
            eda_base_url=eda_base_url.strip().rstrip("/"),
            company=company.strip(),
            division=division.strip(),
            language=language.strip(),
            output_dir=output_dir.strip(),
        )
        self.ctx.storage.save(data)
        return self._config()

    @action
    def cancel(self) -> None:
        with self._lock:
            self._job.cancel.set()

    # --- connexion -----------------------------------------------------------------

    @action
    def login(self, target: Target) -> None:
        config = self._config()
        if target == "eda":
            if not config.eda_base_url:
                raise ToolError("base_url_required", "M3 URL is required")
            url, matcher = eda.portal_url(config.eda_base_url), eda.matcher()
        else:
            tenant = check_tenant(config.tenant)
            url = {
                "mashup": mashup.portal_url,
                "xtend": xtend.portal_url,
                "workspaces": workspaces.portal_url,
            }[target](tenant)
            matcher = {
                "mashup": mashup.matcher,
                "xtend": xtend.matcher,
                "workspaces": workspaces.matcher,
            }[target]()

        def work(job: _Job) -> None:
            self._sessions[target] = capture_session(
                url,
                matcher,
                on_status=lambda status: self._update(job, status=status),
                should_cancel=job.cancel.is_set,
            )
            self._update(job, status="connected")

        self._start(f"login_{target}", work)

    @action
    def set_token(self, token: str) -> None:
        """Onglet workspaces : jeton de session portail collé à la main."""
        self._sessions["workspaces"] = workspaces.manual_session(token)

    @action
    def logout(self, target: Target) -> None:
        self._sessions.pop(target, None)

    # --- Export EDA ----------------------------------------------------------------

    @action
    def eda_list(self) -> list[eda.EdaItem]:
        return self._guard("eda", lambda s: eda.list_edas(s))

    @action
    def eda_export(self, edas: str) -> None:
        names = eda.parse_edas(edas)
        if not names:
            raise ToolError("no_eda", "No EDA given")
        session = self._session("eda")
        config = self._config()
        out = self._out("eda")

        def work(job: _Job) -> None:
            out.mkdir(parents=True, exist_ok=True)
            self._update(job, status="working", total=len(names))
            for i, name in enumerate(names, 1):
                if job.cancel.is_set():
                    self._log(job, "cancelled")
                    break
                try:
                    data = eda.fetch_eda(
                        session, name, config.company, config.division, config.language
                    )
                    eda.file_for(out, name).write_text(
                        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    self._update(job, ok=job.ok + 1)
                except ToolError as exc:
                    if exc.code == "session_expired":
                        self._expired("eda")
                        raise
                    self._update(job, failed=job.failed + 1)
                    self._log(job, f"ERR {name}: {exc.message}")
                self._update(job, done=i)
            self._update(job, status="finished")

        self._start("eda_export", work)

    # --- Mashups -------------------------------------------------------------------

    @action
    def mashup_list(self) -> list[mashup.Mashup]:
        return self._guard("mashup", lambda s: mashup.list_apps(s))

    # --- Workspaces et widgets -----------------------------------------------------

    @action
    def ws_list(
        self, kind: Literal["workspaces", "insights"], query: str = ""
    ) -> list[workspaces.Workspace]:
        tenant = check_tenant(self._config().tenant)
        items = self._guard("workspaces", lambda s: workspaces.list_items(s, tenant, kind, query))
        self._ws_titles.update({i.id: i.title for i in items})
        return items

    @action
    def ws_analyze(self, ids: list[str]) -> None:
        if not ids:
            raise ToolError("nothing_selected", "Nothing selected")
        tenant = check_tenant(self._config().tenant)
        session = self._session("workspaces")

        def work(job: _Job) -> None:
            # Un export par workspace : un workspace non publié donne une archive vide, ce qui
            # ne doit pas faire perdre les autres (le serveur n'exporte que les versions publiées).
            self._update(job, status="working", total=len(ids))
            occurrences: list[workspaces.Occurrence] = []
            for i, ws_id in enumerate(ids, 1):
                if job.cancel.is_set():
                    self._log(job, "cancelled")
                    break
                label = self._ws_titles.get(ws_id, ws_id)
                try:
                    data = workspaces.export_zip(session, tenant, [ws_id])
                    report: list[str] = []
                    found = workspaces.widgets_in_zip(data, report)
                except ToolError as exc:
                    if exc.code == "session_expired":
                        self._expired("workspaces")
                        raise
                    self._update(job, failed=job.failed + 1)
                    self._log(job, f"ERR {label}: {exc.message}")
                else:
                    occurrences.extend(found)
                    if found:
                        self._update(job, ok=job.ok + 1)
                    else:
                        self._update(job, failed=job.failed + 1)
                        detail = "; ".join(report[:3]) or f"{len(data)} bytes"
                        self._log(job, f"0 widget {label} ({detail})")
                self._update(job, done=i)
            totals, rows = workspaces.aggregate(occurrences)
            self._ws_result = WsResult(totals=totals, rows=rows)
            self._update(job, status="finished")

        self._start("ws_analyze", work)

    @action
    def ws_result(self) -> WsResult:
        return self._ws_result

    @action
    def ws_export_csv(self) -> str:
        if not self._ws_result.rows:
            raise ToolError("nothing_to_export", "Nothing to export")
        path = self._out("widgets") / f"widgets_{datetime.now():%Y%m%d_%H%M%S}.csv"
        workspaces.write_csv(path, self._ws_result.rows)
        return str(path)

    # --- Export CSV d'un tableau ---------------------------------------------------

    @action
    def save_csv(self, name: str, header: list[str], rows: list[list[str | int]]) -> str:
        """Écrit un tableau affiché en CSV (`;`, utf-8-sig) dans le sous-dossier csv."""
        if not rows:
            raise ToolError("nothing_to_export", "Nothing to export")
        stem = eda.safe_name(name).strip() or "export"
        path = self._out("csv") / f"{stem}_{datetime.now():%Y%m%d_%H%M%S}.csv"
        workspaces.write_table_csv(path, header, rows)
        return str(path)

    # --- Code Xtend ----------------------------------------------------------------

    @action
    def xtend_list(self) -> list[xtend.Source]:
        refs = self._guard("xtend", lambda s: xtend.list_programs(s))
        self._xtend_sources = {r.uuid: r for r in refs}
        return refs

    @action
    def xtend_fetch(self, uuids: list[str]) -> None:
        """Récupère le code des sources données (toutes celles listées si `uuids` est vide)."""
        if not self._xtend_sources:
            raise ToolError("nothing_listed", "List the programs first")
        wanted = [self._xtend_sources[u] for u in uuids if u in self._xtend_sources]
        refs = wanted if uuids else list(self._xtend_sources.values())
        if not refs:
            raise ToolError("nothing_selected", "Nothing selected")
        session = self._session("xtend")
        store = xtend.CodeStore(self._out("xtend"))

        def work(job: _Job) -> None:
            self._update(job, status="working", total=len(refs))
            try:
                for i, ref in enumerate(refs, 1):
                    if job.cancel.is_set():
                        self._log(job, "cancelled")
                        break
                    try:
                        store.save(ref, xtend.get_code(session, ref))
                        self._update(job, ok=job.ok + 1)
                    except ToolError as exc:
                        if exc.code == "session_expired":
                            self._expired("xtend")
                            raise
                        self._update(job, failed=job.failed + 1)
                        self._log(job, f"ERR {ref.program}/{ref.name}: {exc.message}")
                    self._update(job, done=i)
            finally:
                store.flush()
            self._update(job, status="finished")

        self._start("xtend_fetch", work)

    @action
    def xtend_search(
        self,
        query: str,
        regex: bool = False,
        case_sensitive: bool = False,
        kinds: list[str] | None = None,
    ) -> list[xtend.Hit]:
        wanted = set(kinds) if kinds is not None else set(xtend.KINDS)
        return xtend.search(
            self._out("xtend"), query, regex=regex, case_sensitive=case_sensitive, kinds=wanted
        )

    @action
    def xtend_read(self, file: str) -> str:
        return xtend.read_code(self._out("xtend"), file)


SERVICE = M3Service
