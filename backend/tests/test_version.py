import re
import tomllib

from wrench._version import __version__
from wrench.core import paths


def test_version_matches_pyproject() -> None:
    pyproject = paths.resource_dir() / "backend" / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text("utf-8"))
    assert data["project"]["version"] == __version__


def test_version_format() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?", __version__)
