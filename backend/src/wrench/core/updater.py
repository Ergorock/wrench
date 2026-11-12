import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import winreg
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from wrench._version import __version__

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
CHUNK_SIZE = 64 * 1024

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


def check_url(url: str) -> None:
    """Refuse anything but https on an allowed host (userinfo tricks resolve to the real host)."""
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
        raise UpdateError("update_integrity", f"URL not allowed: {url}")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpClient(Protocol):
    def get_json(self, url: str) -> Any: ...

    def download(self, url: str, dest: Path, on_progress: Callable[[int, int], None]) -> None: ...


class UrllibClient:
    def __init__(self, opener: Any = None) -> None:
        self._opener = opener or urllib.request.build_opener(SafeRedirectHandler)

    def _request(self, url: str) -> Any:
        check_url(url)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"Wrench/{__version__}",
                "Accept": "application/vnd.github+json",
            },
        )
        return self._opener.open(req, timeout=TIMEOUT_S)

    def get_json(self, url: str) -> Any:
        """Invalid JSON is reported as update_network (the server answered garbage)."""
        try:
            with self._request(url) as resp:
                return json.loads(resp.read())
        except UpdateError:
            raise  # integrity refusal from check_url / redirect handler
        except (OSError, ValueError) as e:  # URLError, HTTPError, TimeoutError are OSError
            raise UpdateError("update_network", str(e)) from e

    def download(self, url: str, dest: Path, on_progress: Callable[[int, int], None]) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._request(url) as resp, dest.open("wb") as out:
                total = int(resp.headers.get("Content-Length") or 0)
                received = 0
                while chunk := resp.read(CHUNK_SIZE):
                    out.write(chunk)
                    received += len(chunk)
                    on_progress(received, total)
        except BaseException as e:
            dest.unlink(missing_ok=True)
            if isinstance(e, UpdateError):
                raise
            if isinstance(e, (OSError, ValueError)):
                raise UpdateError("update_network", str(e)) from e
            raise


def verify_file(path: Path, size: int, sha256: str) -> None:
    """Check size then SHA-256; on mismatch delete the file and raise update_integrity."""
    digest = hashlib.sha256()
    try:
        ok = path.stat().st_size == size
        if ok:
            with path.open("rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    digest.update(chunk)
            ok = digest.hexdigest() == sha256.lower()
    except OSError as e:
        raise UpdateError("update_integrity", f"Cannot read downloaded file: {e}") from e
    if not ok:
        path.unlink(missing_ok=True)
        raise UpdateError("update_integrity", "Downloaded file failed verification")
