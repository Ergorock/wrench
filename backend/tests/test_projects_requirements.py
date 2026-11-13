from collections.abc import Sequence
from pathlib import Path

from wrench.tools.projects.requirements import Requirement, Runner, check, collect

README = (
    "# Wrench\r\n\r\nIntro.\r\n\r\n## Prérequis\r\n\r\n"
    "- Python 3.12 et [uv](https://docs.astral.sh/uv/)\r\n"
    "- Node.js 22 ou plus récent\r\n"
    "- Runtime WebView2 de Microsoft (présent par défaut sur Windows 11)\r\n\r\n"
    "## Installation\r\n\r\n- Git 2.0\r\n"
)
WEBVIEW = "Runtime WebView2 de Microsoft (présent par défaut sur Windows 11)"


def rows(items: list[Requirement]) -> list[tuple[str, str | None, str, str]]:
    return [(r.tool, r.required, r.status, r.source) for r in items]


def test_collect_reads_sources_and_skips_broken_ones(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"\n')
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "package.json").write_text("{ not json")
    (tmp_path / "README.md").write_bytes(b"\xef\xbb\xbf" + README.encode())
    items = collect(tmp_path)
    assert rows(items) == [
        ("Python", ">=3.12", "unknown", "pyproject.toml"),
        ("uv", None, "unknown", "uv.lock"),
        ("Node.js", ">=22", "unknown", "README.md"),
        (WEBVIEW, None, "manual", "README.md"),
    ]
    assert all(r.installed is None for r in items)


def test_collect_invalid_pyproject_keeps_other_sources(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project\nbroken")
    (tmp_path / ".python-version").write_text("3.12.4\n")
    assert rows(collect(tmp_path)) == [("Python", "==3.12", "unknown", ".python-version")]


def test_collect_standard_files(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"engines": {"node": ">=20", "npm": "^10"}, "packageManager": "pnpm@9.1.0+sha512.abc"}'
    )
    (tmp_path / ".nvmrc").write_text("v18.2.0\n")
    (tmp_path / "global.json").write_text('{"sdk": {"version": "8.0.100"}}')
    (tmp_path / "Cargo.toml").write_text('[package]\nrust-version = "1.75"\n')
    (tmp_path / "go.mod").write_text("module x\n\ngo 1.22\n")
    (tmp_path / ".git").mkdir()
    assert rows(collect(tmp_path)) == [
        ("Node.js", ">=20", "unknown", "package.json"),
        ("npm", "^10", "unknown", "package.json"),
        ("pnpm", ">=9.1.0", "unknown", "package.json"),
        (".NET SDK", ">=8.0.100", "unknown", "global.json"),
        ("Rust", ">=1.75", "unknown", "Cargo.toml"),
        ("Go", ">=1.22", "unknown", "go.mod"),
        ("git", None, "unknown", ".git"),
    ]


def test_collect_nvmrc_when_no_package_json(tmp_path: Path) -> None:
    (tmp_path / ".nvmrc").write_text("v18.2.0\n")
    assert rows(collect(tmp_path)) == [("Node.js", "18.2.0", "unknown", ".nvmrc")]


def test_collect_csproj_is_presence_only(tmp_path: Path) -> None:
    (tmp_path / "App.csproj").write_text("<Project/>")
    assert rows(collect(tmp_path)) == [(".NET SDK", None, "unknown", "App.csproj")]


def test_collect_readme_title_variants_and_stop(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "### Requirements\n* git\n* `Go` >= 1.21\n## Usage\n- Node 22\n"
    )
    assert rows(collect(tmp_path)) == [
        ("git", None, "unknown", "README.md"),
        ("Go", ">=1.21", "unknown", "README.md"),
    ]
    (tmp_path / "README.md").write_text("## dependances\n- Java 17+\n# Next\n- uv\n")
    assert rows(collect(tmp_path)) == [("Java", ">=17", "unknown", "README.md")]


def test_collect_standard_source_wins_over_readme(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("go 1.22\n")
    (tmp_path / "README.md").write_text("## Prerequisites\n- Go 1.18\n- Go\n")
    assert rows(collect(tmp_path)) == [("Go", ">=1.22", "unknown", "go.mod")]


def test_collect_empty_project(tmp_path: Path) -> None:
    assert collect(tmp_path) == []


def fake(outputs: dict[str, str | None]) -> tuple[list[Sequence[str]], Runner]:
    calls: list[Sequence[str]] = []

    def run(cmd: Sequence[str]) -> str | None:
        calls.append(cmd)
        return outputs.get(cmd[0])

    return calls, run


def test_check_statuses(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"\n')
    (tmp_path / "package.json").write_text('{"engines": {"node": ">=22", "npm": ">=1 || >=2"}}')
    (tmp_path / "go.mod").write_text("go 1.22\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("## Prerequisites\n- Runtime X\n")
    calls, run = fake({"py": "Python 3.12.4", "node": "v20.1.0", "npm": "10.2.0", "go": None})
    items = {r.tool: r for r in check(tmp_path, run)}
    assert (items["Python"].status, items["Python"].installed) == ("ok", "3.12.4")
    assert (items["Node.js"].status, items["Node.js"].installed) == ("too_old", "20.1.0")
    assert (items["npm"].status, items["npm"].installed) == ("unknown", "10.2.0")
    assert (items["Go"].status, items["Go"].installed) == ("missing", None)
    assert items["git"].status == "missing"
    assert items["Runtime X"].status == "manual"
    assert not any("Runtime X" in c[0] for c in calls)
    assert ["py", "-3", "--version"] in [list(c) for c in calls]


def test_check_python_falls_back_to_python_command(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"\n')
    _calls, run = fake({"py": None, "python": "Python 3.13.0"})
    [item] = check(tmp_path, run)
    assert (item.status, item.installed) == ("ok", "3.13.0")


def test_check_python_version_file_compares_major_minor(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("3.12.4\n")
    _calls, run = fake({"py": "Python 3.12.9"})
    assert check(tmp_path, run)[0].status == "ok"
    _calls, run = fake({"py": "Python 3.13.0"})
    assert check(tmp_path, run)[0].status == "too_old"


def test_check_reads_java_combined_output(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("## Requirements\n- Java 17+\n")
    _calls, run = fake({"java": 'openjdk version "21.0.1" 2023-10-17\nOpenJDK Runtime'})
    [item] = check(tmp_path, run)
    assert (item.status, item.installed) == ("ok", "21.0.1")


def test_check_output_without_version_is_unknown(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    _calls, run = fake({"git": "garbage"})
    [item] = check(tmp_path, run)
    assert (item.status, item.installed) == ("unknown", None)
