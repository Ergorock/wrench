import logging
from pathlib import Path

import pytest

from wrench.sdk import ToolContext, ToolError, ToolStorage
from wrench.tools.dev_tools.service import DevToolsService


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        "dev_tools",
        ToolStorage(tmp_path / "dev_tools.json"),
        lambda: "en",
        logging.getLogger("test"),
    )


@pytest.fixture
def svc(ctx: ToolContext) -> DevToolsService:
    return DevToolsService(ctx)


def test_base64_round_trip_with_accents(svc):
    encoded = svc.invoke("encode_base64", {"text": "Café ✓"})
    assert encoded == "Q2Fmw6kg4pyT"
    assert svc.invoke("decode_base64", {"text": encoded}) == "Café ✓"


def test_base64_decode_ignores_line_breaks(svc):
    assert svc.invoke("decode_base64", {"text": "Q2Fm\nw6k="}) == "Café"


def test_base64_decode_rejects_invalid_input(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("decode_base64", {"text": "pas du base64 !"})
    assert e.value.code == "invalid_base64"


def test_url_encode_and_decode(svc):
    assert svc.invoke("encode_url", {"text": "a b&c=d/é"}) == "a%20b%26c%3Dd%2F%C3%A9"
    assert svc.invoke("decode_url", {"text": "a%20b%26c%3Dd"}) == "a b&c=d"


@pytest.mark.parametrize(
    ("value", "hex_", "rgb", "hsl"),
    [
        ("#fff", "#FFFFFF", [255, 255, 255], [0, 0, 100]),
        ("00ff00", "#00FF00", [0, 255, 0], [120, 100, 50]),
        ("#1E90FF", "#1E90FF", [30, 144, 255], [210, 100, 56]),
        ("#000", "#000000", [0, 0, 0], [0, 0, 0]),
    ],
)
def test_convert_color(svc, value, hex_, rgb, hsl):
    info = svc.invoke("convert_color", {"color": value})
    assert info == {"hex": hex_, "rgb": rgb, "hsl": hsl}


@pytest.mark.parametrize("value", ["#ggg", "#12345", "rouge", ""])
def test_convert_color_rejects_invalid_hex(svc, value):
    with pytest.raises(ToolError) as e:
        svc.invoke("convert_color", {"color": value})
    assert e.value.code == "invalid_color"


def test_format_json_indents_and_keeps_accents(svc):
    out = svc.invoke("format_json", {"text": '{"a":1,"b":[true,"é"]}'})
    assert out == '{\n  "a": 1,\n  "b": [\n    true,\n    "é"\n  ]\n}'


def test_format_json_minify(svc):
    out = svc.invoke("format_json", {"text": '{\n  "a": 1,\n  "b": [true]\n}', "minify": True})
    assert out == '{"a":1,"b":[true]}'


def test_format_json_reports_position(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("format_json", {"text": '{"a": }'})
    assert e.value.code == "invalid_json"
    assert "line 1" in e.value.message


def test_format_xml_reindents_and_keeps_comments(svc):
    source = '<?xml version="1.0"?><root><!-- note --><item id="1">texte</item><empty/></root>'
    out = svc.invoke("format_xml", {"text": source})
    assert out == (
        '<?xml version="1.0" ?>\n'
        "<root>\n"
        "  <!-- note -->\n"
        '  <item id="1">texte</item>\n'
        "  <empty/>\n"
        "</root>"
    )


def test_format_xml_reindents_already_indented_input(svc):
    source = "<root>\n    <a>1</a>\n    <b>2</b>\n</root>"
    out = svc.invoke("format_xml", {"text": source})
    assert out == '<?xml version="1.0" ?>\n<root>\n  <a>1</a>\n  <b>2</b>\n</root>'


def test_format_xml_rejects_invalid_input(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("format_xml", {"text": "<a><b></a>"})
    assert e.value.code == "invalid_xml"
