import io
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

import barcode
import segno
from barcode.errors import BarcodeError
from barcode.writer import SVGWriter
from pydantic import BaseModel, Field

from wrench.sdk import ToolError, ToolService, action

MAX_DATA = 1000
BARCODE_TYPES: dict[str, str] = {"code128": "code128", "code39": "code39", "ean13": "ean13"}
_UNSAFE_NAME = re.compile(r"[^\w\- ]+")


class Symbol(BaseModel):
    kind: Literal["qr", "barcode"]
    data: str = Field(max_length=MAX_DATA)
    # Only used for barcodes: code128, code39 or ean13.
    barcode_type: str = "code128"


class Picture(BaseModel):
    svg: str


class Exported(BaseModel):
    path: str


def _render(symbol: Symbol) -> bytes:
    """The SVG file content, built from the symbol alone."""
    if symbol.data == "":
        raise ToolError("empty_data", "Enter some text first.")
    buffer = io.BytesIO()
    if symbol.kind == "qr":
        # MAX_DATA stays well under a QR code's capacity at level M, so this cannot overflow.
        segno.make(symbol.data, error="m").save(buffer, kind="svg", scale=8, border=4)
        return buffer.getvalue()
    if symbol.barcode_type not in BARCODE_TYPES:
        raise ToolError("unknown_barcode_type", f"Unknown barcode type: {symbol.barcode_type}")
    try:
        barcode.get(BARCODE_TYPES[symbol.barcode_type], symbol.data, writer=SVGWriter()).write(
            buffer
        )
    except BarcodeError as e:
        raise ToolError("invalid_barcode_data", str(e)) from e
    return buffer.getvalue()


class QrBarcodeService(ToolService):
    @action
    def generate(self, symbol: Symbol) -> Picture:
        return Picture(svg=_render(symbol).decode("utf-8"))

    @action
    def export(self, symbol: Symbol, folder: str, name: str) -> Exported:
        """Write the symbol as an SVG file in `folder`. An existing file is never overwritten."""
        target_dir = Path(folder)
        if not target_dir.is_dir():
            raise ToolError("folder_not_found", f"Folder not found: {folder}")
        content = _render(symbol)
        stamp = datetime.now().strftime("code-%Y%m%d-%H%M%S")
        base = _UNSAFE_NAME.sub("", name).strip()[:60] or stamp
        path = target_dir / f"{base}.svg"
        counter = 2
        while path.exists():
            path = target_dir / f"{base} ({counter}).svg"
            counter += 1
        path.write_bytes(content)
        return Exported(path=str(path))


SERVICE = QrBarcodeService
