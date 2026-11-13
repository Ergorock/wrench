import pytest

from wrench.tools.projects.versions import parse_version, satisfies


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Python 3.12.4", (3, 12, 4)),
        ("v20.1.0", (20, 1, 0)),
        ("go version go1.22.1 windows/amd64", (1, 22, 1)),
        ('openjdk version "21.0.1" 2023-10-17', (21, 0, 1)),
        ("22", (22,)),
        ("no digits here", None),
        ("", None),
    ],
)
def test_parse_version(text: str, expected: tuple[int, ...] | None) -> None:
    assert parse_version(text) == expected


@pytest.mark.parametrize(
    ("installed", "constraint", "expected"),
    [
        ((3, 12, 4), ">=3.12", True),
        ((3, 11), ">=3.12", False),
        ((3, 12), ">= 3.12", True),
        ((3, 12), ">3.12", False),
        ((3, 12, 1), ">3.12", True),
        ((3, 12), "<=3.12", True),
        ((3, 13), "<3.13", False),
        ((3, 12), "==3.12", True),
        ((3, 12, 4), "==3.12", False),
        ((3, 13), "==3.12", False),
        ((3, 12, 4), "~=3.12", True),
        ((4, 0), "~=3.12", False),
        ((3, 13, 0), "~=3.12.1", False),
        ((3, 12, 5), "~=3.12.1", True),
        ((22, 11), "^20", False),
        ((20, 5), "^20", True),
        ((1, 9), "^1.2", True),
        ((2, 0), "^1.2", False),
        ((0, 3, 9), "^0.3", True),
        ((0, 4), "^0.3", False),
        ((1, 2, 9), "~1.2.3", True),
        ((1, 3, 0), "~1.2.3", False),
        ((1, 2, 2), "~1.2.3", False),
        ((3, 12, 7), "3.12.x", True),
        ((3, 13), "3.12.x", False),
        ((3, 12), "3.12.*", True),
        ((22, 1), "22", True),
        ((20, 1), "22", False),
        ((3, 12), ">=3.10,<3.13", True),
        ((3, 13), ">=3.10 <3.13", False),
        ((5, 0), "*", True),
        ((18, 0), ">=18 || >=20", None),
        ((18, 0), "latest", None),
    ],
)
def test_satisfies(installed: tuple[int, ...], constraint: str, expected: bool | None) -> None:
    assert satisfies(installed, constraint) is expected
