"""Amounts are decimal strings at API boundaries; never infer currency from '$'."""
from decimal import Decimal, InvalidOperation

from sqlalchemy import Numeric, String
from sqlalchemy.types import TypeDecorator

CURRENCIES = {"USD": 2, "EUR": 2, "COP": 2, "JPY": 0}


def currency_code(value: str) -> str:
    if value not in CURRENCIES:
        raise ValueError("Moneda no admitida. Usa USD, EUR, COP o JPY.")
    return value


def amount(value, currency: str) -> Decimal:
    currency_code(currency)
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result <= 0 or result >= Decimal("10000000000000000"):
            raise ValueError("Precio fuera de rango.")
        unit = Decimal(1).scaleb(-CURRENCIES[currency])
        rounded = result.quantize(unit)
        if result != rounded:
            raise ValueError("Precisión incompatible con la moneda.")
        return rounded
    except InvalidOperation as exc:
        raise ValueError("Precio inválido.") from exc


class Money(TypeDecorator):
    """SQLite has no exact decimal: use TEXT there, NUMERIC on PostgreSQL."""
    impl = Numeric(20, 4)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(String(48) if dialect.name == "sqlite" else Numeric(20, 4))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return format(Decimal(str(value)), "f") if dialect.name == "sqlite" else Decimal(str(value))

    def process_result_value(self, value, dialect):
        return Decimal(str(value)) if value is not None else None
