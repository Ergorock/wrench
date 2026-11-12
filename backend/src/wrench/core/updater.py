import logging
import os
import re
import winreg
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger("wrench.updater")

REPO = "Ergorock/wrench"
API_URL = "https://api.github.com/repos/Ergorock/wrench/releases/latest"
ASSET_PATTERN = r"^Wrench-Setup-(\d+\.\d+\.\d+)\.exe$"
ALLOWED_HOSTS = {
    "github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
TIMEOUT_S = 10
INSTALLER_ARGS = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH"]
UNINSTALL_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    r"\{DF1A711B-045E-48E1-A43E-DCBD79719B83}_is1"
)
INSTALL_LOCATION_VALUE = "InstallLocation"

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(-[0-9A-Za-z.\-]+)?$")
_DIGEST_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


class UpdateError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class UpdateInfo(BaseModel):
    version: str
    notes_url: str
    asset_url: str
    size: int
    sha256: str


def parse_version(s: str) -> tuple[int, int, int, bool] | None:
    """Parse "X.Y.Z" or "X.Y.Z-suffix"; the boolean is True for a test (suffixed) version."""
    m = _VERSION_RE.match(s)
    if m is None:
        return None
    return int(m[1]), int(m[2]), int(m[3]), m[4] is not None


def is_newer(remote: str, local: str) -> bool:
    """True if `remote` is strictly newer than `local`.

    At equal numbers a final release beats a pre-release. An unparseable `remote` is never
    newer; an unparseable `local` is not updated either (conservative: unknown state, no offer).
    """
    r = parse_version(remote)
    loc = parse_version(local)
    if r is None or loc is None:
        return False
    return (r[:3], not r[3]) > (loc[:3], not loc[3])


def select_update(release: dict[str, Any], local_version: str) -> UpdateInfo | None:
    if release.get("draft") or release.get("prerelease"):
        return None
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not tag.startswith("v"):
        return None
    version = tag[1:]
    parsed = parse_version(version)
    if parsed is None or parsed[3] or not is_newer(version, local_version):
        return None
    for asset in release.get("assets") or []:
        name = asset.get("name", "")
        m = re.match(ASSET_PATTERN, name)
        if m is None or m[1] != version:
            continue
        digest = _DIGEST_RE.match(str(asset.get("digest") or ""))
        size = asset.get("size")
        url = asset.get("browser_download_url")
        if digest is None or not isinstance(size, int) or not isinstance(url, str):
            logger.warning("Release %s: asset %s has no usable digest/size/url", tag, name)
            return None
        return UpdateInfo(
            version=version,
            notes_url=str(release.get("html_url", "")),
            asset_url=url,
            size=size,
            sha256=digest[1].lower(),
        )
    logger.warning("Release %s: no matching installer asset", tag)
    return None


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def update_supported(
    exe: str, frozen: bool, read_install_location: Callable[[], str | None]
) -> bool:
    """Updates only apply to a frozen exe running from the folder the installer registered."""
    if not frozen:
        return False
    location = read_install_location()
    if not location:
        return False
    return _norm(os.path.dirname(exe)) == _norm(location)


def read_install_location() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            value, _ = winreg.QueryValueEx(key, INSTALL_LOCATION_VALUE)
    except OSError:
        return None
    return value if isinstance(value, str) and value else None
