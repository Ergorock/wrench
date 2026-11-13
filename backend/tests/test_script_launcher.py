import logging
import sys
from pathlib import Path

import pytest

from wrench.sdk import ToolContext, ToolError, ToolStorage
from wrench.tools.script_launcher import service as launcher
from wrench.tools.script_launcher.service import ScriptLauncherService


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        "script_launcher",
        ToolStorage(tmp_path / "script_launcher.json"),
        lambda: "en",
        logging.getLogger("test"),
    )


@pytest.fixture
def svc(ctx: ToolContext) -> ScriptLauncherService:
    return ScriptLauncherService(ctx)


def python_command(code: str, cwd: str = "") -> dict[str, object]:
    return {
        "name": "Python",
        "program": sys.executable,
        "args": ["-c", code],
        "cwd": cwd,
    }


def test_save_then_list(svc):
    saved = svc.invoke("save_command", {"command": python_command("print(1)")})
    assert len(saved["commands"]) == 1
    cid = saved["commands"][0]["id"]
    assert len(cid) == 32
    assert svc.invoke("list_commands", {})["commands"][0]["id"] == cid


def test_update_keeps_id_and_position(svc):
    svc.invoke("save_command", {"command": {"name": "A", "program": "a.exe"}})
    svc.invoke("save_command", {"command": {"name": "B", "program": "b.exe"}})
    first = svc.invoke("list_commands", {})["commands"][0]
    svc.invoke(
        "save_command",
        {"command": {"id": first["id"], "name": "A2", "program": "a2.exe"}},
    )
    commands = svc.invoke("list_commands", {})["commands"]
    assert [c["name"] for c in commands] == ["A2", "B"]
    assert commands[0]["id"] == first["id"]


def test_update_unknown_id_is_refused(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("save_command", {"command": {"id": "nope", "name": "A", "program": "a.exe"}})
    assert e.value.code == "unknown_command"


def test_blank_name_or_program_is_refused(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("save_command", {"command": {"name": "   ", "program": "a.exe"}})
    assert e.value.code == "invalid_command"


def test_missing_cwd_is_refused_on_save(svc, tmp_path):
    with pytest.raises(ToolError) as e:
        svc.invoke(
            "save_command",
            {"command": {"name": "A", "program": "a.exe", "cwd": str(tmp_path / "absent")}},
        )
    assert e.value.code == "folder_not_found"


def test_delete(svc):
    cid = svc.invoke("save_command", {"command": {"name": "A", "program": "a.exe"}})["commands"][0][
        "id"
    ]
    assert svc.invoke("delete_command", {"command_id": cid})["commands"] == []
    with pytest.raises(ToolError) as e:
        svc.invoke("delete_command", {"command_id": cid})
    assert e.value.code == "unknown_command"


def test_run_captures_output_and_exit_code(svc):
    code = "import sys; print('hi'); sys.exit(3)"
    saved = svc.invoke("save_command", {"command": python_command(code)})
    result = svc.invoke("run_command", {"command_id": saved["commands"][0]["id"]})
    # Windows may turn \n into \r\n in the captured output.
    assert result["exit_code"] == 3
    assert result["timed_out"] is False
    assert result["stdout"].strip() == "hi"
    assert result["stderr"] == ""


def test_run_uses_saved_working_folder(svc, tmp_path):
    saved = svc.invoke(
        "save_command",
        {"command": python_command("import os; print(os.getcwd())", cwd=str(tmp_path))},
    )
    result = svc.invoke("run_command", {"command_id": saved["commands"][0]["id"]})
    assert Path(result["stdout"].strip()).resolve() == tmp_path.resolve()


def test_run_times_out(svc, monkeypatch):
    monkeypatch.setattr(launcher, "TIMEOUT_SECONDS", 0.5)
    saved = svc.invoke("save_command", {"command": python_command("import time; time.sleep(10)")})
    result = svc.invoke("run_command", {"command_id": saved["commands"][0]["id"]})
    assert result["timed_out"] is True
    assert result["exit_code"] is None


def test_missing_program_is_reported(svc):
    saved = svc.invoke(
        "save_command", {"command": {"name": "Ghost", "program": "definitely-not-here.exe"}}
    )
    with pytest.raises(ToolError) as e:
        svc.invoke("run_command", {"command_id": saved["commands"][0]["id"]})
    assert e.value.code == "program_not_found"


def test_arguments_are_not_passed_through_a_shell(svc, monkeypatch):
    seen: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["shell"] = kwargs.get("shell")

        class Done:
            returncode = 0
            stdout = b""
            stderr = b""

        return Done()

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)
    saved = svc.invoke(
        "save_command",
        {"command": {"name": "Echo", "program": "tool.exe", "args": ["a & del x", " "]}},
    )
    svc.invoke("run_command", {"command_id": saved["commands"][0]["id"]})
    assert seen == {"argv": ["tool.exe", "a & del x"], "shell": False}


def test_malformed_stored_entries_are_ignored(ctx):
    ctx.storage.save(
        {
            "commands": [
                {"id": "x", "name": "", "program": "a.exe"},
                {"name": "Ok", "program": "b.exe"},
            ]
        }
    )
    names = [c["name"] for c in ScriptLauncherService(ctx).invoke("list_commands", {})["commands"]]
    assert names == ["Ok"]
