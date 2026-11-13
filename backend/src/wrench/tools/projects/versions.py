"""Version parsing and constraint comparison (spec 4.6). Pure: nothing is run or read here."""

import re

Version = tuple[int, ...]

_VERSION = re.compile(r"\d+(?:\.\d+)*")
_SPACE_AFTER_OP = re.compile(r"(~=|==|>=|<=|[<>^~=])\s+")
_TOKEN = re.compile(r"^(~=|==|>=|<=|[<>^~=])?v?(\d+(?:\.\d+)*)(\.[x*])?$", re.IGNORECASE)


def parse_version(text: str) -> Version | None:
    """The first dotted number of `text`."""
    match = _VERSION.search(text)
    return tuple(int(p) for p in match.group().split(".")) if match else None


def _cmp(a: Version, b: Version) -> int:
    size = max(len(a), len(b))
    a, b = a + (0,) * (size - len(a)), b + (0,) * (size - len(b))
    return (a > b) - (a < b)


def _bump(version: Version, index: int) -> Version:
    return (*version[:index], version[index] + 1)


def _one(installed: Version, token: str) -> bool | None:
    if token in ("*", "x", "X"):
        return True
    match = _TOKEN.match(token)
    if match is None:
        return None
    op, text, wildcard = match.groups()
    version = tuple(int(p) for p in text.split("."))
    if wildcard:  # 3.12.x: same prefix
        return installed[: len(version)] == version
    if op in (None, ">="):  # a bare number reads as "at least"
        return _cmp(installed, version) >= 0
    if op == ">":
        return _cmp(installed, version) > 0
    if op == "<=":
        return _cmp(installed, version) <= 0
    if op == "<":
        return _cmp(installed, version) < 0
    if op in ("==", "="):
        return _cmp(installed, version) == 0
    if op == "~=":  # PEP 440: ~=3.12 is >=3.12,<4 ; ~=3.12.1 is >=3.12.1,<3.13
        upper = _bump(version, max(len(version) - 2, 0))
    elif op == "^":  # npm: the first non-zero component may not change
        index = next((i for i, n in enumerate(version) if n), len(version) - 1)
        upper = _bump(version, index)
    else:  # "~", npm: ~1.2.3 and ~1.2 are <1.3, ~1 is <2
        upper = _bump(version, 1 if len(version) > 1 else 0)
    return _cmp(installed, version) >= 0 and _cmp(installed, upper) < 0


def satisfies(installed: Version, constraint: str) -> bool | None:
    """True or False, or None when the constraint cannot be compared (`||`, free text)."""
    if "||" in constraint:
        return None
    tokens = [t for t in re.split(r"[,\s]+", _SPACE_AFTER_OP.sub(r"\1", constraint.strip())) if t]
    if not tokens:
        return None
    results = [_one(installed, t) for t in tokens]
    if False in results:
        return False
    return None if None in results else True
