import math
import re
from collections.abc import Callable
from datetime import date

from pydantic import BaseModel

from wrench.sdk import ToolError, ToolService, action

BASE_CURRENCY = "EUR"
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
TEMPERATURE = "temperature"

# Factor of each unit to the base unit of its category (metre, kilogram, litre…).
UNITS: dict[str, dict[str, float]] = {
    "length": {
        "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
        "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344,
    },  # fmt: skip
    "mass": {
        "mg": 1e-6, "g": 0.001, "kg": 1.0, "t": 1000.0,
        "oz": 0.028349523125, "lb": 0.45359237,
    },  # fmt: skip
    "volume": {
        "ml": 0.001, "cl": 0.01, "l": 1.0, "m3": 1000.0,
        "fl_oz_us": 0.0295735295625, "gal_us": 3.785411784,
    },  # fmt: skip
    "area": {
        "cm2": 1e-4, "m2": 1.0, "ha": 10000.0, "km2": 1e6,
        "ft2": 0.09290304, "acre": 4046.8564224,
    },  # fmt: skip
    "speed": {"m_s": 1.0, "km_h": 1 / 3.6, "mph": 0.44704, "kn": 0.514444},
    "data": {
        "B": 1.0, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12,
        "KiB": 1024.0, "MiB": 1024.0**2, "GiB": 1024.0**3,
    },  # fmt: skip
}

# Temperatures are not proportional: each unit has a conversion to and from kelvin.
TEMPERATURE_TO_KELVIN: dict[str, Callable[[float], float]] = {
    "C": lambda v: v + 273.15,
    "F": lambda v: (v - 32) * 5 / 9 + 273.15,
    "K": lambda v: v,
}
TEMPERATURE_FROM_KELVIN: dict[str, Callable[[float], float]] = {
    "C": lambda k: k - 273.15,
    "F": lambda k: (k - 273.15) * 9 / 5 + 32,
    "K": lambda k: k,
}


class UnitCategory(BaseModel):
    id: str
    units: list[str]


class Units(BaseModel):
    categories: list[UnitCategory]


class Rate(BaseModel):
    code: str
    rate: float
    date: str


class Rates(BaseModel):
    base: str
    rates: list[Rate]


def _check_value(value: float) -> None:
    if not math.isfinite(value):
        raise ToolError("invalid_value", "The value must be a finite number.")


class ConvertersService(ToolService):
    def _rates(self) -> dict[str, Rate]:
        """Stored rates, ignoring malformed entries."""
        stored = self.ctx.storage.load().get("rates", {})
        if not isinstance(stored, dict):
            return {}
        result: dict[str, Rate] = {}
        for code, item in stored.items():
            if not isinstance(item, dict) or not _CURRENCY_RE.match(str(code)):
                continue
            rate, day = item.get("rate"), item.get("date")
            if isinstance(rate, (int, float)) and rate > 0 and isinstance(day, str):
                result[code] = Rate(code=code, rate=float(rate), date=day)
        return result

    def _save_rates(self, rates: dict[str, Rate]) -> None:
        self.ctx.storage.save(
            {"rates": {r.code: {"rate": r.rate, "date": r.date} for r in rates.values()}}
        )

    def _rates_view(self) -> Rates:
        rates = sorted(self._rates().values(), key=lambda r: r.code)
        return Rates(base=BASE_CURRENCY, rates=rates)

    @action
    def get_units(self) -> Units:
        categories = [UnitCategory(id=cid, units=list(u)) for cid, u in UNITS.items()]
        categories.append(UnitCategory(id=TEMPERATURE, units=list(TEMPERATURE_TO_KELVIN)))
        return Units(categories=categories)

    @action
    def convert_unit(self, category: str, value: float, source: str, target: str) -> float:
        _check_value(value)
        if category == TEMPERATURE:
            if source not in TEMPERATURE_TO_KELVIN or target not in TEMPERATURE_FROM_KELVIN:
                raise ToolError("unknown_unit", "Unknown temperature unit.")
            kelvin = TEMPERATURE_TO_KELVIN[source](value)
            return TEMPERATURE_FROM_KELVIN[target](kelvin)
        factors = UNITS.get(category)
        if factors is None:
            raise ToolError("unknown_category", f"Unknown category: {category}")
        if source not in factors or target not in factors:
            raise ToolError("unknown_unit", "Unknown unit for this category.")
        return value * factors[source] / factors[target]

    @action
    def get_rates(self) -> Rates:
        return self._rates_view()

    @action
    def set_rate(self, code: str, rate: float, day: str) -> Rates:
        if not _CURRENCY_RE.match(code) or code == BASE_CURRENCY:
            raise ToolError("invalid_currency", f"Invalid currency code: {code}")
        if not math.isfinite(rate) or rate <= 0:
            raise ToolError("invalid_rate", "The rate must be a positive number.")
        try:
            date.fromisoformat(day)
        except ValueError as e:
            raise ToolError("invalid_date", f"Invalid date: {day}") from e
        rates = self._rates()
        rates[code] = Rate(code=code, rate=rate, date=day)
        self._save_rates(rates)
        return self._rates_view()

    @action
    def remove_rate(self, code: str) -> Rates:
        rates = self._rates()
        rates.pop(code, None)
        self._save_rates(rates)
        return self._rates_view()

    @action
    def convert_currency(self, value: float, source: str, target: str) -> float:
        _check_value(value)
        rates = self._rates()
        factors = {BASE_CURRENCY: 1.0} | {code: r.rate for code, r in rates.items()}
        for code in (source, target):
            if code not in factors:
                raise ToolError("unknown_currency", f"Unknown currency: {code}")
        # rate = units of the currency for 1 EUR, so value / rate gives EUR.
        return value / factors[source] * factors[target]


SERVICE = ConvertersService
