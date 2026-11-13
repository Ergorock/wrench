"""Prerequisites of a project: read from its standard files and README (spec 4.6), then checked
by running ONLY the version command of each known tool. Nothing of the project is ever run."""

import json
import re
import subprocess
import tomllib
import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel

from wrench.tools.projects.versions import parse_version, satisfies

COMMAND_TIMEOUT = 10
READ_ERRORS = (OSError, ValueError, tomllib.TOMLDecodeError)  # UnicodeDecodeError is a ValueError


class ToolSpec(NamedTuple):
    label: str
    aliases: tuple[str, ...]
    commands: tuple[tuple[str, ...], ...]  # tried in order until one answers


KNOWN_TOOLS: dict[str, ToolSpec] = {
    "python": ToolSpec("Python", ("python",), (("py", "-3", "--version"), ("python", "--version"))),
    "uv": ToolSpec("uv", ("uv",), (("uv", "--version"),)),
    "node": ToolSpec("Node.js", ("node", "node.js"), (("node", "--version"),)),
    "npm": ToolSpec("npm", ("npm",), (("npm", "--version"),)),
    "pnpm": ToolSpec("pnpm", ("pnpm",), (("pnpm", "--version"),)),
    "yarn": ToolSpec("yarn", ("yarn",), (("yarn", "--version"),)),
    "git": ToolSpec("git", ("git",), (("git", "--version"),)),
    "dotnet": ToolSpec(".NET SDK", (".net", "dotnet"), (("dotnet", "--version"),)),
    "rust": ToolSpec("Rust", ("rust", "cargo"), (("cargo", "--version"),)),
    "go": ToolSpec("Go", ("go", "golang"), (("go", "version"),)),
    "java": ToolSpec("Java", ("java", "jdk"), (("java", "-version"),)),
}
_BY_LABEL = {spec.label: spec for spec in KNOWN_TOOLS.values()}

Runner = Callable[[Sequence[str]], str | None]


class Requirement(BaseModel):
    tool: str
    required: str | None
    installed: str | None
    status: Literal["ok", "too_old", "missing", "unknown", "manual"]
    source: str


def run_version(command: Sequence[str]) -> str | None:
    """Combined stdout and stderr of a version command; None when it is not found or too slow."""
    try:
        done = subprocess.run(  # noqa: S603 - an explicit list from KNOWN_TOOLS, no shell
            list(command),
            capture_output=True,
            timeout=COMMAND_TIMEOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (done.stdout + b"\n" + done.stderr).decode("utf-8", errors="replace")


# --- reading the sources -------------------------------------------------------------


class _Found:
    """The requirements found so far: a tool appears once, the first source wins."""

    def __init__(self) -> None:
        self.items: list[Requirement] = []
        self._seen: set[str] = set()

    def add(self, key: str, required: str | None, source: str) -> None:
        if key in self._seen:
            return
        self._seen.add(key)
        self.items.append(
            Requirement(
                tool=KNOWN_TOOLS[key].label,
                required=required,
                installed=None,
                status="unknown",
                source=source,
            )
        )


def _json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} is not an object")
    return data


def _at_least(version: str) -> str | None:
    parsed = parse_version(version)
    return ">=" + ".".join(map(str, parsed)) if parsed else None


def _pyproject(folder: Path, found: _Found) -> None:
    path = folder / "pyproject.toml"
    uses_uv = False
    if path.is_file():
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except READ_ERRORS:
            data = {}
        project, tool = data.get("project"), data.get("tool")
        requires = project.get("requires-python") if isinstance(project, dict) else None
        if isinstance(requires, str) and requires.strip():
            found.add("python", requires.strip(), "pyproject.toml")
        uses_uv = isinstance(tool, dict) and "uv" in tool
    if (folder / "uv.lock").is_file():
        found.add("uv", None, "uv.lock")
    elif uses_uv:
        found.add("uv", None, "pyproject.toml")


def _python_version(folder: Path, found: _Found) -> None:
    text = (folder / ".python-version").read_text(encoding="utf-8-sig").strip()
    version = parse_version(text.splitlines()[0]) if text else None
    if version:
        found.add("python", "==" + ".".join(map(str, version[:2])), ".python-version")


def _package_json(folder: Path, found: _Found) -> None:
    data = _json(folder / "package.json")
    engines = data.get("engines")
    if isinstance(engines, dict):
        for key in ("node", "npm", "pnpm", "yarn"):
            value = engines.get(key)
            if isinstance(value, str) and value.strip():
                found.add(key, value.strip(), "package.json")
    manager = data.get("packageManager")
    if isinstance(manager, str) and "@" in manager:
        name, _, version = manager.partition("@")
        if name in ("npm", "pnpm", "yarn") and (required := _at_least(version)):
            found.add(name, required, "package.json")


def _node_version_file(name: str) -> Callable[[Path, _Found], None]:
    def read(folder: Path, found: _Found) -> None:
        text = (folder / name).read_text(encoding="utf-8-sig").strip()
        line = text.splitlines()[0].strip() if text else ""
        if re.fullmatch(r"v?\d+(\.\d+)*", line):
            found.add("node", line.removeprefix("v"), name)

    return read


def _global_json(folder: Path, found: _Found) -> None:
    sdk = _json(folder / "global.json").get("sdk")
    version = sdk.get("version") if isinstance(sdk, dict) else None
    if isinstance(version, str) and (required := _at_least(version)):
        found.add("dotnet", required, "global.json")


def _csproj(folder: Path, found: _Found) -> None:
    for path in sorted(folder.glob("*.csproj")):
        found.add("dotnet", None, path.name)  # presence only
        return


def _cargo(folder: Path, found: _Found) -> None:
    with (folder / "Cargo.toml").open("rb") as handle:
        package = tomllib.load(handle).get("package")
    version = package.get("rust-version") if isinstance(package, dict) else None
    if isinstance(version, str) and (required := _at_least(version)):
        found.add("rust", required, "Cargo.toml")


def _go_mod(folder: Path, found: _Found) -> None:
    text = (folder / "go.mod").read_text(encoding="utf-8-sig")
    match = re.search(r"^go\s+(\d+(?:\.\d+)*)", text, re.MULTILINE)
    if match and (required := _at_least(match.group(1))):
        found.add("go", required, "go.mod")


def _git(folder: Path, found: _Found) -> None:
    if (folder / ".git").exists():
        found.add("git", None, ".git")


# --- README --------------------------------------------------------------------------

_HEADING = re.compile(r"^#{1,6}\s")
_PREREQ_HEADING = re.compile(r"^#{2,3}\s+(.*?)\s*#*\s*$")
_PREREQ_TITLES = {"prerequis", "prerequisites", "requirements", "dependances"}
_ITEM = re.compile(r"^\s*[-*]\s+(.*\S)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_CONSTRAINT = re.compile(r"^(>=|<=|==|~=|[<>^~])\s*v?(\d+(?:\.\d+)*)|^v?(\d+(?:\.\d+)*)")
_ALIASES = sorted(
    ((alias, key) for key, spec in KNOWN_TOOLS.items() for alias in spec.aliases),
    key=lambda pair: -len(pair[0]),
)


def _plain(text: str) -> str:
    """Drops the Markdown links and emphasis of a list line."""
    return re.sub(r"[*_`]", "", _LINK.sub(r"\1", text)).strip()


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip(" :")


def _readme_lines(folder: Path) -> list[str]:
    """The list lines of the first prerequisites section, up to the next heading."""
    text = (folder / "README.md").read_text(encoding="utf-8-sig")  # universal newlines
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        if _HEADING.match(line):
            if inside:
                break
            heading = _PREREQ_HEADING.match(line)
            inside = bool(heading and _fold(heading.group(1)) in _PREREQ_TITLES)
        elif inside and (item := _ITEM.match(line)):
            lines.append(_plain(item.group(1)))
    return lines


def _readme(folder: Path, found: _Found) -> None:
    for line in _readme_lines(folder):
        lowered = line.lower()
        for alias, key in _ALIASES:
            if lowered.startswith(alias) and not re.match(r"[\w.]", lowered[len(alias) :][:1]):
                required = _constraint(line[len(alias) :].strip())
                found.add(key, required, "README.md")
                break
        else:
            found.items.append(
                Requirement(
                    tool=line, required=None, installed=None, status="manual", source="README.md"
                )
            )


def _constraint(text: str) -> str | None:
    """`>= 3.12`, `3.12+`, `22 ou plus récent`, `^20` or a bare number (at least)."""
    match = _CONSTRAINT.match(text)
    if match is None:
        return None
    if match.group(2):
        return match.group(1) + match.group(2)
    return ">=" + match.group(3)


_SOURCES: tuple[Callable[[Path, _Found], None], ...] = (
    _pyproject,
    _python_version,
    _package_json,
    _node_version_file(".nvmrc"),
    _node_version_file(".node-version"),
    _global_json,
    _csproj,
    _cargo,
    _go_mod,
    _git,
    _readme,
)


def collect(folder: Path) -> list[Requirement]:
    """What the project asks for, with provisional `unknown` status; an unreadable source is
    skipped and the others are still read."""
    found = _Found()
    for source in _SOURCES:
        try:
            source(folder, found)
        except READ_ERRORS:
            continue
    return found.items


# --- checking ------------------------------------------------------------------------


def _installed(spec: ToolSpec, run: Runner) -> tuple[bool, tuple[int, ...] | None]:
    """(the tool answered, its version)."""
    answered = False
    for command in spec.commands:
        output = run(command)
        if output is None:
            continue
        answered = True
        version = parse_version(output)
        if version:
            return True, version
    return answered, None


def _check_one(item: Requirement, run: Runner) -> Requirement:
    answered, version = _installed(_BY_LABEL[item.tool], run)
    if not answered:
        return item.model_copy(update={"status": "missing"})
    if version is None:
        return item.model_copy(update={"status": "unknown"})
    installed = ".".join(map(str, version))
    if item.required is None:
        return item.model_copy(update={"installed": installed, "status": "ok"})
    # .python-version is exact: compared on major.minor only.
    compared = version[:2] if item.source == ".python-version" else version
    verdict = satisfies(compared, item.required)
    status = "unknown" if verdict is None else "ok" if verdict else "too_old"
    return item.model_copy(update={"installed": installed, "status": status})


def check(folder: Path, run: Runner = run_version) -> list[Requirement]:
    """`collect`, then the installed version and the status of every known tool. `manual`
    lines run nothing."""
    return [item if item.status == "manual" else _check_one(item, run) for item in collect(folder)]
