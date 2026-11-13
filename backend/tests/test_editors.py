from pathlib import Path

from wrench.shared.editors import Editor, command_for, exe_exists


def test_command_for_expands_and_substitutes(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", r"C:\L")
    e = Editor(id="k", name="Kiro", exe=r"%LOCALAPPDATA%\Kiro.exe", args=["{path}"])
    assert command_for(e, Path(r"C:\Dev\Été")) == [r"C:\L\Kiro.exe", r"C:\Dev\Été"]


def test_shell_target_ignores_args():
    e = Editor(id="c", name="Claude", exe=r"shell:AppsFolder\X!Y", args=["{path}"])
    assert command_for(e, Path(r"C:\p")) == ["explorer.exe", r"shell:AppsFolder\X!Y"]
    assert exe_exists(e) is True


def test_exe_exists_false_for_missing(tmp_path):
    assert exe_exists(Editor(id="x", name="X", exe=str(tmp_path / "no.exe"))) is False
