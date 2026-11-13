import io
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from PIL import Image

from wrench.shared.winicon import encode_png, icon_png


def test_encode_png_roundtrip() -> None:
    png = encode_png(2, 1, bytes([0, 0, 255, 255, 255, 0, 0, 128]))  # red opaque, blue half
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.mode == "RGBA"
    assert img.getpixel((0, 0)) == (255, 0, 0, 255)
    assert img.getpixel((1, 0)) == (0, 0, 255, 128)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API")
def test_icon_png_notepad() -> None:
    png = icon_png(r"%SystemRoot%\System32\notepad.exe")
    assert png is not None
    assert Image.open(io.BytesIO(png)).size == (32, 32)


def test_icon_png_missing_file(tmp_path: Path) -> None:
    assert icon_png(str(tmp_path / "absent.exe")) is None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API")
def test_icon_png_shell_target_on_a_thread_without_com() -> None:
    # SHParseDisplayName on `shell:AppsFolder` fails (path not found) unless COM is
    # initialized on the calling thread; API worker threads do not do it.
    result: list[bytes | None] = []
    thread = threading.Thread(
        target=lambda: result.append(icon_png(r"shell:AppsFolder\Microsoft.Windows.Explorer"))
    )
    thread.start()
    thread.join()
    assert result[0] is not None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API")
def test_icon_png_concurrent_cold_start() -> None:
    # The app asks for every editor icon at once on its first screen; unserialized
    # first calls made SHGetFileInfoW fail for one of them (and None is cached).
    vscode = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"))
    if not vscode.is_file():
        pytest.skip("VS Code not installed")
    claude = r"shell:AppsFolder\Claude_pzs8sxrjxfjjc!Claude"
    notepad = r"%SystemRoot%\System32\notepad.exe"
    script = "\n".join(
        [
            "import sys, threading",
            "from wrench.shared.winicon import icon_png",
            "out = {}",
            "def run(t): out[t] = icon_png(t)",
            "ts = [threading.Thread(target=run, args=(t,)) for t in sys.argv[1:]]",
            "[t.start() for t in ts]",
            "[t.join() for t in ts]",
            "print(len(out[sys.argv[1]] or b''), out[sys.argv[2]] is not None)",
        ]
    )
    for _ in range(8):  # each run is a fresh process, hence a cold start
        done = subprocess.run(
            [sys.executable, "-c", script, str(vscode), claude, notepad],
            capture_output=True,
            text=True,
            check=True,
        )
        size, claude_ok = done.stdout.split()
        assert int(size) > 500
        assert claude_ok == "True"
