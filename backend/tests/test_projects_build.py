import json
from pathlib import Path

import pytest

from wrench.tools.projects.build import suggest_build

PS = "powershell -ExecutionPolicy Bypass -File scripts/build.ps1"
BUILD = '{"scripts": {"build": "x"}}'


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"scripts/build.ps1": ""}, PS),
        ({"package.json": BUILD}, "npm run build"),
        ({"package.json": BUILD, "pnpm-lock.yaml": ""}, "pnpm run build"),
        ({"package.json": BUILD, "yarn.lock": ""}, "yarn run build"),
        (
            {"package.json": '{"scripts": {"build": "x"}, "packageManager": "pnpm@9.1.0"}'},
            "pnpm run build",
        ),
        ({"package.json": '{"scripts": {"test": "x"}}'}, None),
        ({"package.json": "not json"}, None),
        ({"pyproject.toml": "", "uv.lock": ""}, "uv build"),
        ({"pyproject.toml": ""}, None),
        ({"App.sln": ""}, "dotnet build"),
        ({"Cargo.toml": ""}, "cargo build"),
        ({"go.mod": ""}, "go build ./..."),
        ({}, None),
    ],
)
def test_suggest_build(tmp_path: Path, files: dict[str, str], expected: str | None) -> None:
    for name, content in files.items():
        f = tmp_path / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    assert suggest_build(tmp_path) == expected


def test_script_wins_over_package_json(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "build.ps1").write_text("", encoding="utf-8")
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"build": "x"}}))
    assert suggest_build(tmp_path) == PS
