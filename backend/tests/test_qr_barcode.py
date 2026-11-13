import logging
from pathlib import Path

import pytest

from wrench.sdk import ToolContext, ToolError, ToolStorage
from wrench.tools.qr_barcode.service import QrBarcodeService


@pytest.fixture
def svc(tmp_path: Path) -> QrBarcodeService:
    ctx = ToolContext(
        "qr_barcode",
        ToolStorage(tmp_path / "qr_barcode.json"),
        lambda: "en",
        logging.getLogger("test"),
    )
    return QrBarcodeService(ctx)


def sym(kind: str, data: str, barcode_type: str = "code128") -> dict[str, str]:
    return {"kind": kind, "data": data, "barcode_type": barcode_type}


def test_qr_svg_is_generated(svc):
    svg = svc.invoke("generate", {"symbol": sym("qr", "https://example.com")})["svg"]
    assert svg.lstrip().startswith("<?xml") or svg.lstrip().startswith("<svg")
    assert "<svg" in svg


def test_barcode_svg_is_generated_for_each_type(svc):
    for kind, data in [("code128", "ABC-123"), ("code39", "ABC-123"), ("ean13", "590123412345")]:
        svg = svc.invoke("generate", {"symbol": sym("barcode", data, kind)})["svg"]
        assert "<svg" in svg


def test_empty_data_is_refused(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("generate", {"symbol": sym("qr", "")})
    assert e.value.code == "empty_data"


def test_longest_accepted_text_still_fits_a_qr(svc):
    svg = svc.invoke("generate", {"symbol": sym("qr", "é" * 1000)})["svg"]
    assert "<svg" in svg


def test_invalid_ean13_is_refused(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("generate", {"symbol": sym("barcode", "12a", "ean13")})
    assert e.value.code == "invalid_barcode_data"


def test_unknown_barcode_type_is_refused(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("generate", {"symbol": sym("barcode", "123", "upc")})
    assert e.value.code == "unknown_barcode_type"


def test_export_writes_svg_in_folder(svc, tmp_path):
    out = svc.invoke(
        "export",
        {"symbol": sym("qr", "hello"), "folder": str(tmp_path), "name": "mon code"},
    )
    path = Path(out["path"])
    assert path == tmp_path / "mon code.svg"
    assert "<svg" in path.read_text(encoding="utf-8")


def test_export_never_overwrites(svc, tmp_path):
    args = {"symbol": sym("qr", "hello"), "folder": str(tmp_path), "name": "code"}
    first = svc.invoke("export", args)["path"]
    second = svc.invoke("export", args)["path"]
    assert first != second
    assert Path(second).name == "code (2).svg"


def test_export_sanitizes_name(svc, tmp_path):
    out = svc.invoke(
        "export",
        {"symbol": sym("qr", "hi"), "folder": str(tmp_path), "name": "../../evil"},
    )
    assert Path(out["path"]).parent == tmp_path
    assert Path(out["path"]).name == "evil.svg"


def test_export_refuses_missing_folder(svc, tmp_path):
    with pytest.raises(ToolError) as e:
        svc.invoke(
            "export",
            {"symbol": sym("qr", "hi"), "folder": str(tmp_path / "absent"), "name": "x"},
        )
    assert e.value.code == "folder_not_found"
