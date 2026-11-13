import io
import sys
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
