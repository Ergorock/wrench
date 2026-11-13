import logging
import math
from pathlib import Path

import pytest

from wrench.sdk import ToolContext, ToolError, ToolStorage
from wrench.tools.converters.service import ConvertersService


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        "converters",
        ToolStorage(tmp_path / "converters.json"),
        lambda: "en",
        logging.getLogger("test"),
    )


@pytest.fixture
def svc(ctx: ToolContext) -> ConvertersService:
    return ConvertersService(ctx)


def convert(svc, category, value, source, target):
    return svc.invoke(
        "convert_unit",
        {"category": category, "value": value, "source": source, "target": target},
    )


def test_units_are_listed_by_category(svc):
    ids = [c["id"] for c in svc.invoke("get_units", {})["categories"]]
    assert ids == ["length", "mass", "volume", "area", "speed", "data", "temperature"]


def test_length_and_mass(svc):
    assert convert(svc, "length", 1, "km", "m") == pytest.approx(1000)
    assert convert(svc, "length", 12, "in", "ft") == pytest.approx(1)
    assert convert(svc, "mass", 1, "lb", "kg") == pytest.approx(0.45359237)


def test_data_binary_and_decimal(svc):
    assert convert(svc, "data", 1, "KiB", "B") == pytest.approx(1024)
    assert convert(svc, "data", 1, "GB", "MB") == pytest.approx(1000)


def test_temperatures_are_not_proportional(svc):
    assert convert(svc, "temperature", 100, "C", "F") == pytest.approx(212)
    assert convert(svc, "temperature", 32, "F", "C") == pytest.approx(0)
    assert convert(svc, "temperature", 0, "C", "K") == pytest.approx(273.15)
    assert convert(svc, "temperature", -40, "C", "F") == pytest.approx(-40)


def test_round_trip_keeps_value(svc):
    there = convert(svc, "speed", 90, "km_h", "mph")
    assert convert(svc, "speed", there, "mph", "km_h") == pytest.approx(90)


def test_unknown_category_and_unit(svc):
    with pytest.raises(ToolError) as e:
        convert(svc, "power", 1, "W", "kW")
    assert e.value.code == "unknown_category"
    with pytest.raises(ToolError) as e:
        convert(svc, "length", 1, "m", "kg")
    assert e.value.code == "unknown_unit"
    with pytest.raises(ToolError) as e:
        convert(svc, "temperature", 1, "C", "m")
    assert e.value.code == "unknown_unit"


def test_non_finite_value_is_rejected(svc):
    with pytest.raises(ToolError) as e:
        convert(svc, "length", math.nan, "m", "km")
    assert e.value.code == "invalid_value"


def test_set_rate_stores_and_lists_sorted(svc):
    svc.invoke("set_rate", {"code": "USD", "rate": 1.08, "day": "2026-11-13"})
    rates = svc.invoke("set_rate", {"code": "GBP", "rate": 0.87, "day": "2026-11-12"})
    assert rates["base"] == "EUR"
    assert [r["code"] for r in rates["rates"]] == ["GBP", "USD"]


def test_set_rate_validation(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("set_rate", {"code": "usd", "rate": 1.0, "day": "2026-11-13"})
    assert e.value.code == "invalid_currency"
    with pytest.raises(ToolError) as e:
        svc.invoke("set_rate", {"code": "EUR", "rate": 1.0, "day": "2026-11-13"})
    assert e.value.code == "invalid_currency"
    with pytest.raises(ToolError) as e:
        svc.invoke("set_rate", {"code": "USD", "rate": 0, "day": "2026-11-13"})
    assert e.value.code == "invalid_rate"
    with pytest.raises(ToolError) as e:
        svc.invoke("set_rate", {"code": "USD", "rate": 1.0, "day": "13/11/2026"})
    assert e.value.code == "invalid_date"


def test_currency_conversion_goes_through_eur(svc):
    svc.invoke("set_rate", {"code": "USD", "rate": 2.0, "day": "2026-11-13"})
    svc.invoke("set_rate", {"code": "GBP", "rate": 0.5, "day": "2026-11-13"})
    assert svc.invoke("convert_currency", {"value": 10, "source": "EUR", "target": "USD"}) == 20
    assert svc.invoke("convert_currency", {"value": 10, "source": "USD", "target": "EUR"}) == 5
    assert svc.invoke(
        "convert_currency", {"value": 10, "source": "USD", "target": "GBP"}
    ) == pytest.approx(2.5)


def test_unknown_currency(svc):
    with pytest.raises(ToolError) as e:
        svc.invoke("convert_currency", {"value": 1, "source": "EUR", "target": "JPY"})
    assert e.value.code == "unknown_currency"


def test_remove_rate(svc):
    svc.invoke("set_rate", {"code": "USD", "rate": 1.08, "day": "2026-11-13"})
    assert svc.invoke("remove_rate", {"code": "USD"})["rates"] == []


def test_malformed_stored_rates_are_ignored(ctx):
    ctx.storage.save(
        {
            "rates": {
                "USD": {"rate": 1.08, "date": "2026-11-13"},
                "BAD": {"rate": -1, "date": "2026-11-13"},
                "XYZ": "nope",
                "lower": {"rate": 1, "date": "2026-11-13"},
            }
        }
    )
    rates = ConvertersService(ctx).invoke("get_rates", {})["rates"]
    assert [r["code"] for r in rates] == ["USD"]
