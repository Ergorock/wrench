import base64
import io
import json
import logging
import time
import zipfile
from pathlib import Path
from typing import Any

import pytest

from wrench.sdk import ToolContext, ToolError, ToolStorage
from wrench.tools.m3 import eda, http, mashup, workspaces, xtend
from wrench.tools.m3.service import M3Service
from wrench.tools.m3.session import RequestMatcher, Session


class FakeResponse:
    def __init__(self, payload: Any = None, status: int = 200, headers: dict | None = None):
        self._payload = payload
        self.status_code = status
        self.ok = 200 <= status < 300
        self.text = json.dumps(payload) if payload is not None else ""
        self.headers = headers or {}
        self.content = b""

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


@pytest.fixture
def svc(tmp_path: Path) -> M3Service:
    ctx = ToolContext(
        "m3", ToolStorage(tmp_path / "m3.json"), lambda: "en", logging.getLogger("test")
    )
    service = M3Service(ctx)
    service.invoke(
        "set_config",
        {
            "tenant": "TEN_TST",
            "eda_base_url": "https://m3.example.com/",
            "company": "100",
            "division": "CF0",
            "language": "FR",
            "output_dir": str(tmp_path / "out"),
        },
    )
    return service


def wait_idle(svc: M3Service) -> dict:
    for _ in range(200):
        state = svc.invoke("get_state", {})
        if not state["job"]["running"]:
            return state["job"]
        time.sleep(0.01)
    raise AssertionError("job still running")


# --- session / http --------------------------------------------------------------------


def test_matcher_keeps_latest_request_with_the_header():
    m = RequestMatcher("/mnerest/", "mua_csrf_token")
    m.feed("https://h/other", {"mua_csrf_token": "x"})
    m.feed("https://h/mnerest/a", {})
    assert not m.ready
    m.feed("https://h/mnerest/a", {"MUA_CSRF_TOKEN": "t1"})
    m.feed("https://h/mnerest/b", {"mua_csrf_token": "t2"})
    assert m.ready and m.base_url == "https://h" and m.headers == {"mua_csrf_token": "t2"}


def test_http_maps_401_to_session_expired(monkeypatch):
    monkeypatch.setattr(http.requests, "request", lambda *a, **k: FakeResponse({}, 401))
    with pytest.raises(ToolError) as e:
        http.call("GET", Session("https://h"), "/x", referer="/")
    assert e.value.code == "session_expired"


def test_http_html_body_means_expired_session():
    with pytest.raises(ToolError) as e:
        http.json_of(FakeResponse(None))
    assert e.value.code == "session_expired"


# --- EDA -------------------------------------------------------------------------------


def test_parse_edas_skips_header_blanks_and_duplicates():
    assert eda.parse_edas("EDA\nA1;x\n\n B2 \nA1\n") == ["A1", "B2"]


def test_eda_safe_name():
    assert eda.safe_name('a/b:c*"') == "a_b_c__"


# --- mashup ----------------------------------------------------------------------------


def test_parse_apps_and_bad_payload():
    payload = {
        "content": {
            "apps": [
                {
                    "name": "App",
                    "description": None,
                    "category": 1,
                    "visibility": 2,
                    "createdBy": "a",
                    "changedBy": "b",
                    "changeDate": "2026-01-01T00:00:00UTC",
                }
            ]
        }
    }
    apps = mashup.parse_apps(payload)
    assert apps[0].name == "App" and apps[0].description == ""
    with pytest.raises(ToolError) as e:
        mashup.parse_apps({"content": {}})
    assert e.value.code == "bad_response"


def test_mashup_url_rejects_bad_tenant():
    with pytest.raises(ToolError) as e:
        mashup.portal_url("a b")
    assert e.value.code == "invalid_tenant"


# --- Xtend -----------------------------------------------------------------------------


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def program_info() -> dict:
    return {
        "programModules": {
            "EXT001": {
                "program": "EXT001",
                "batches": {"B1": {"sourceUuid": "u-b", "name": "B1", "modified": 5}},
                "transactions": {"Get": {"sourceUuid": "u-t", "description": "d"}},
                "triggers": {"T": {"sourceUuid": "ignored"}},
            }
        }
    }


def test_parse_program_info_keeps_batches_and_transactions():
    refs = xtend.parse_program_info(program_info())
    assert [(r.kind, r.uuid) for r in refs] == [("batch", "u-b"), ("transaction", "u-t")]


def test_decode_code_sources_and_fallback():
    assert xtend.decode_code({"sources": {"u": {"code": b64("é = 1")}}}, "u") == "é = 1"
    assert xtend.decode_code({"code": b64("x")}, "u") == "x"
    with pytest.raises(ToolError):
        xtend.decode_code({"sources": {}}, "u")


def test_store_search_and_read(tmp_path: Path):
    refs = xtend.parse_program_info(program_info())
    store = xtend.CodeStore(tmp_path)
    store.save(refs[0], "a\r\nfoo(1)\r\n")
    store.save(refs[1], "bar()\n")
    store.flush()
    hits = xtend.search(tmp_path, "FOO", regex=False, case_sensitive=False, kinds={"batch"})
    assert [(h.kind, h.line) for h in hits] == [("batch", 2)]
    assert (
        xtend.search(tmp_path, "FOO", regex=False, case_sensitive=True, kinds=set(xtend.KINDS))
        == []
    )
    assert xtend.read_code(tmp_path, hits[0].file) == "a\r\nfoo(1)\r\n"
    with pytest.raises(ToolError):
        xtend.read_code(tmp_path, "../x.groovy")
    with pytest.raises(ToolError) as e:
        xtend.search(tmp_path, "(", regex=True, case_sensitive=False, kinds={"batch"})
    assert e.value.code == "invalid_regex"


def test_file_name_avoids_reserved_names():
    source = xtend.Source(
        uuid="u", program="CON", kind="batch", name="n", description="", modified=0, modified_by=""
    )
    assert xtend.file_name_for(source).startswith("_CON_")


# --- Workspaces ------------------------------------------------------------------------


def export_zip() -> bytes:
    def page(pid: str, title: str, widgets: list[tuple[str, str]]) -> str:
        nodes = [{"type": "widget", "ref": {"id": w}, "data": {"title": t}} for w, t in widgets]
        return json.dumps(
            {
                "id": pid,
                "title": title,
                "dashboard": {"containers": [{"nodes": [{"type": "layout", "nodes": nodes}]}]},
            }
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("p1.json", page("1", "WS1", [("mon", "Monitor"), ("mon", "Monitor")]))
        z.writestr("p2.json", page("2", "WS2", [("mon", ""), ("kpi", "KPI")]))
        z.writestr("readme.txt", "ignored")
    return buf.getvalue()


def test_widgets_aggregate_and_csv(tmp_path: Path):
    totals, rows = workspaces.aggregate(workspaces.widgets_in_zip(export_zip()))
    assert [(t.widget_id, t.count) for t in totals] == [("mon", 3), ("kpi", 1)]
    assert totals[0].label == "Monitor"
    assert [(r.workspace_title, r.widget_id, r.count) for r in rows] == [
        ("WS1", "mon", 2),
        ("WS2", "kpi", 1),
        ("WS2", "mon", 1),
    ]
    path = tmp_path / "w.csv"
    workspaces.write_csv(path, rows)
    assert path.read_text(encoding="utf-8-sig").splitlines()[1] == "mon;Monitor;WS1;1;2"


def test_manual_token_strips_bearer():
    assert workspaces.manual_session("Bearer abc").headers == {
        workspaces.TOKEN_HEADER: "Bearer abc"
    }
    with pytest.raises(ToolError):
        workspaces.manual_session("  ")


# --- service ---------------------------------------------------------------------------


def test_actions_need_a_session(svc: M3Service):
    for name, payload in [
        ("mashup_list", {}),
        ("ws_list", {"kind": "insights"}),
        ("xtend_list", {}),
        ("eda_export", {"edas": "A"}),
    ]:
        with pytest.raises(ToolError) as e:
            svc.invoke(name, payload)
        assert e.value.code == "not_connected"


def test_login_stores_session(svc: M3Service, monkeypatch):
    seen = {}

    def fake_capture(url, matcher, *, on_status, should_cancel):
        seen["url"] = url
        return Session("https://h", {"c": "v"}, {})

    monkeypatch.setattr("wrench.tools.m3.service.capture_session", fake_capture)
    svc.invoke("login", {"target": "mashup"})
    job = wait_idle(svc)
    assert job["error"] is None and job["status"] == "connected"
    assert "TEN_TST" in seen["url"]
    assert svc.invoke("get_state", {})["connected"]["mashup"] is True


def test_login_error_is_reported_and_busy_is_refused(svc: M3Service, monkeypatch):
    def failing(url, matcher, *, on_status, should_cancel):
        while not should_cancel():
            time.sleep(0.01)
        raise ToolError("login_cancelled", "cancelled")

    monkeypatch.setattr("wrench.tools.m3.service.capture_session", failing)
    svc.invoke("login", {"target": "xtend"})
    with pytest.raises(ToolError) as e:
        svc.invoke("login", {"target": "eda"})
    assert e.value.code == "busy"
    svc.invoke("cancel", {})
    assert wait_idle(svc)["error"]["code"] == "login_cancelled"


def test_login_requires_tenant(tmp_path: Path):
    ctx = ToolContext("m3", ToolStorage(tmp_path / "x.json"), lambda: "en", logging.getLogger("t"))
    with pytest.raises(ToolError) as e:
        M3Service(ctx).invoke("login", {"target": "xtend"})
    assert e.value.code == "tenant_required"


def test_eda_export_writes_files_and_counts_errors(svc: M3Service, monkeypatch, tmp_path: Path):
    svc.invoke("set_token", {"token": "t"})  # sans effet sur eda : on injecte la session
    svc._sessions["eda"] = Session("https://h", {}, {})

    def fake_fetch(session, name, company, division, language, http=None):
        if name == "BAD":
            raise ToolError("http_error", "boom")
        return {"eda": name}

    monkeypatch.setattr("wrench.tools.m3.service.eda.fetch_eda", fake_fetch)
    svc.invoke("eda_export", {"edas": "A\nBAD\nB"})
    job = wait_idle(svc)
    assert (job["ok"], job["failed"], job["done"], job["total"]) == (2, 1, 3, 3)
    assert "ERR BAD: boom" in job["log"]
    assert json.loads((tmp_path / "out" / "eda" / "A.json").read_text("utf-8")) == {"eda": "A"}


def test_expired_session_stops_export_and_disconnects(svc: M3Service, monkeypatch):
    svc._sessions["eda"] = Session("https://h", {}, {})

    def expired(*args, **kwargs):
        raise ToolError("session_expired", "HTTP 401")

    monkeypatch.setattr("wrench.tools.m3.service.eda.fetch_eda", expired)
    svc.invoke("eda_export", {"edas": "A\nB"})
    job = wait_idle(svc)
    assert job["error"]["code"] == "session_expired" and job["done"] == 0
    assert svc.invoke("get_state", {})["connected"]["eda"] is False


def test_xtend_flow(svc: M3Service, monkeypatch, tmp_path: Path):
    svc._sessions["xtend"] = Session("https://h", {}, {})

    def fake_request(method, url, **kwargs):
        if url.endswith("/program/info"):
            return FakeResponse(program_info())
        return FakeResponse({"sources": {url.rsplit("/", 1)[1]: {"code": b64("run()\n")}}})

    monkeypatch.setattr(http.requests, "request", fake_request)
    listed = svc.invoke("xtend_list", {})
    assert len(listed) == 2
    svc.invoke("xtend_fetch", {"uuids": ["u-b"]})
    assert wait_idle(svc)["ok"] == 1
    hits = svc.invoke("xtend_search", {"query": "run"})
    assert len(hits) == 1
    assert svc.invoke("xtend_read", {"file": hits[0]["file"]}) == "run()\n"
    assert (tmp_path / "out" / "xtend" / "manifest.json").is_file()


def test_workspace_analysis_and_csv(svc: M3Service, monkeypatch, tmp_path: Path):
    svc.invoke("set_token", {"token": "tok"})
    monkeypatch.setattr(
        "wrench.tools.m3.service.workspaces.export_zip", lambda *a, **k: export_zip()
    )
    with pytest.raises(ToolError):
        svc.invoke("ws_export_csv", {})
    svc.invoke("ws_analyze", {"ids": ["1", "2"]})
    wait_idle(svc)
    assert [t["widget_id"] for t in svc.invoke("ws_result", {})["totals"]] == ["mon", "kpi"]
    path = Path(svc.invoke("ws_export_csv", {}))
    assert path.parent == tmp_path / "out" / "widgets" and path.is_file()
