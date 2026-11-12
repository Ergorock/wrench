import hashlib
import http.client
import json
import logging
import os
import re
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
import winreg
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Protocol

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
INSTALLER_ARGS = ["/S", "/RELAUNCH"]
UNINSTALL_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    r"\{DF1A711B-045E-48E1-A43E-DCBD79719B83}"
)
INSTALL_LOCATION_VALUE = "InstallLocation"
CHUNK_SIZE = 64 * 1024

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(-[0-9A-Za-z.\-]+)?$")
_DIGEST_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


def _discard(path: Path) -> None:
    """Best-effort delete: a locked file (antivirus, Windows) must never mask the real error."""
    try:
        path.unlink(missing_ok=True)
    except OSError as e:
        logger.warning("Could not delete %s: %s", path, e)


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
    """Accept only plain https://<allowed host>[:443]/... URLs.

    Userinfo ("@" in the netloc) and non-443 ports are refused: urllib does not strip userinfo,
    so what is validated here could otherwise differ from the host urllib connects to.
    """
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError:
        port = -1
    if (
        parsed.scheme != "https"
        or host not in ALLOWED_HOSTS
        or "@" in parsed.netloc
        or port not in (None, 443)
    ):
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
        except (
            OSError,
            ValueError,
            http.client.HTTPException,
        ) as e:  # URLError, HTTPError, TimeoutError are OSError
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
            _discard(dest)
            if isinstance(e, UpdateError):
                raise
            if isinstance(e, (OSError, ValueError, http.client.HTTPException)):
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
        _discard(path)
        raise UpdateError("update_integrity", f"Cannot read downloaded file: {e}") from e
    if not ok:
        _discard(path)
        raise UpdateError("update_integrity", "Downloaded file failed verification")


def launch_installer_detached(path: Path) -> None:
    """Start the installer fully detached so it survives Wrench closing.

    The installer relaunches Wrench (/RELAUNCH) and passes its environment on, so the
    PyInstaller bootloader state of this instance (_PYI_*) is dropped and
    PYINSTALLER_RESET_ENVIRONMENT is set: the new Wrench starts as an independent app.
    """
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("_PYI_")}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen(
        [str(path), *INSTALLER_ARGS],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
        env=env,
    )


UpdateStatus = Literal[
    "idle", "checking", "available", "up_to_date", "downloading", "installing", "error"
]


class Updater:
    """Observable update state; check() is synchronous, start_install() runs in a thread."""

    def __init__(
        self,
        http: HttpClient,
        local_version: str,
        supported: bool,
        download_dir: Path,
        launch_installer: Callable[[Path], None],
        request_close: Callable[[], None] | None = None,
    ) -> None:
        self._http = http
        self._local_version = local_version
        self._supported = supported
        self._download_dir = download_dir
        self._launch_installer = launch_installer
        self._request_close = request_close
        self._lock = threading.Lock()
        self._status: UpdateStatus = "idle"
        self._info: UpdateInfo | None = None
        self._progress = 0.0
        self._error_code: str | None = None
        self._thread: threading.Thread | None = None

    def set_close_handler(self, fn: Callable[[], None]) -> None:
        self._request_close = fn

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> dict[str, Any]:
        return {
            "supported": self._supported,
            "current_version": self._local_version,
            "status": self._status,
            "info": self._info.model_dump() if self._info else None,
            "progress": self._progress,
            "error_code": self._error_code,
        }

    def _require_supported(self) -> None:
        if not self._supported:
            raise UpdateError("update_unsupported", "Updates are not supported for this install")

    def check(self) -> dict[str, Any]:
        self._require_supported()
        with self._lock:
            if self._status in ("downloading", "installing"):
                return self._snapshot_locked()  # never clobber an install in progress
            self._status = "checking"
            self._error_code = None
        info: UpdateInfo | None = None
        error: str | None = None
        try:
            release = self._http.get_json(API_URL)
            if not isinstance(release, dict):
                # A non-object payload is a server answering garbage: same class as bad JSON.
                raise UpdateError("update_network", "Unexpected release payload")
            info = select_update(release, self._local_version)
        except UpdateError as e:
            error = e.code
            logger.warning("Update check failed: %s", e.message)
        except Exception:
            logger.exception("Unexpected error during the update check")
            error = "update_network"
        with self._lock:
            if self._status in ("downloading", "installing"):
                # An install started while this check was in flight: leave it untouched.
                return self._snapshot_locked()
            self._info = info
            self._progress = 0.0
            self._error_code = error
            self._status = "error" if error else ("available" if info else "up_to_date")
            return self._snapshot_locked()

    def start_install(self) -> dict[str, Any]:
        self._require_supported()
        with self._lock:
            if self._info is None:
                raise UpdateError("no_update", "No update available")
            if self._status in ("downloading", "installing"):
                return self._snapshot_locked()
            info = self._info
            self._status = "downloading"
            self._progress = 0.0
            self._error_code = None
            self._thread = threading.Thread(
                target=self._run_install, args=(info,), name="wrench-update", daemon=True
            )
            self._thread.start()
            return self._snapshot_locked()

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _set_error(self, code: str) -> None:
        with self._lock:
            self._status = "error"
            self._error_code = code

    def _on_progress(self, received: int, _total: int, size: int) -> None:
        # Use the size announced by the API (the one we verify), not the HTTP total.
        with self._lock:
            self._progress = min(1.0, max(0.0, received / size)) if size > 0 else 0.0

    def _run_install(self, info: UpdateInfo) -> None:
        path = self._download_dir / f"Wrench-Setup-{info.version}.exe"
        try:
            self._download_dir.mkdir(parents=True, exist_ok=True)
            self._http.download(
                info.asset_url, path, lambda r, t: self._on_progress(r, t, info.size)
            )
            verify_file(path, info.size, info.sha256)  # launch is unreachable if this raises
        except UpdateError as e:
            logger.warning("Update download failed: %s", e.message)
            self._set_error(e.code)
            return
        except Exception:
            logger.exception("Unexpected error while downloading the update")
            _discard(path)
            self._set_error("update_network")
            return
        with self._lock:
            self._status = "installing"
            self._progress = 1.0
        try:
            self._launch_installer(path)
        except Exception:
            logger.exception("Could not launch the installer")
            self._set_error("update_install_failed")
            return
        if self._request_close is None:
            logger.warning("Installer launched but no close handler is set")
            return
        try:
            self._request_close()
        except Exception:
            logger.exception("Close handler failed")
            self._set_error("update_install_failed")
