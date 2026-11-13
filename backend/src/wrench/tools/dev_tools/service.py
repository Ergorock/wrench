import base64
import colorsys
import json
import re
from urllib.parse import quote, unquote
from xml.dom import minidom
from xml.dom.minidom import Node
from xml.parsers.expat import ExpatError

from pydantic import BaseModel

from wrench.sdk import ToolError, ToolService, action

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class ColorInfo(BaseModel):
    hex: str
    rgb: list[int]
    hsl: list[int]


def _parse_hex(value: str) -> tuple[int, int, int]:
    match = _HEX_RE.match(value.strip())
    if match is None:
        raise ToolError("invalid_color", f"Invalid hex color: {value}")
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)


def _strip_blank_text(node: minidom.Element) -> None:
    """Drop whitespace-only text nodes so that toprettyxml does not keep the old indentation."""
    for child in list(node.childNodes):
        if child.nodeType == Node.TEXT_NODE and not child.data.strip():
            node.removeChild(child)
        elif child.nodeType == Node.ELEMENT_NODE:
            _strip_blank_text(child)


class DevToolsService(ToolService):
    @action
    def encode_base64(self, text: str) -> str:
        return base64.b64encode(text.encode("utf-8")).decode("ascii")

    @action
    def decode_base64(self, text: str) -> str:
        # Pasted values often wrap across lines: whitespace is not significant in Base64.
        compact = "".join(text.split())
        try:
            return base64.b64decode(compact, validate=True).decode("utf-8")
        except ValueError as e:  # binascii.Error and UnicodeDecodeError are both ValueError
            raise ToolError("invalid_base64", f"Invalid Base64 input: {e}") from e

    @action
    def encode_url(self, text: str) -> str:
        return quote(text, safe="")

    @action
    def decode_url(self, text: str) -> str:
        return unquote(text)

    @action
    def convert_color(self, color: str) -> ColorInfo:
        r, g, b = _parse_hex(color)
        hue, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        return ColorInfo(
            hex=f"#{r:02X}{g:02X}{b:02X}",
            rgb=[r, g, b],
            hsl=[round(hue * 360) % 360, round(saturation * 100), round(lightness * 100)],
        )

    @action
    def format_json(self, text: str, minify: bool = False) -> str:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ToolError("invalid_json", f"{e.msg} (line {e.lineno}, column {e.colno})") from e
        if minify:
            return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return json.dumps(data, ensure_ascii=False, indent=2)

    @action
    def format_xml(self, text: str) -> str:
        try:
            dom = minidom.parseString(text)
        except ExpatError as e:
            raise ToolError("invalid_xml", str(e)) from e
        root = dom.documentElement
        if root is not None:  # always set after a successful parse
            _strip_blank_text(root)
        return dom.toprettyxml(indent="  ").strip()


SERVICE = DevToolsService
