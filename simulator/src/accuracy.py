from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, ROUND_UP

__all__ = ["increment", "quantize", "round_half_up", "as_end_time"]

precision = Decimal("0")

increment = Decimal("0.5")


def quantize(value) -> Decimal:
    return Decimal(value).quantize(precision, rounding=ROUND_DOWN)


def round_half_up(value) -> Decimal:
    return value.quantize(precision, rounding=ROUND_HALF_UP)


def as_end_time(value: Decimal) -> Decimal:
    if value.is_infinite():
        return value
    return value.quantize(precision, rounding=ROUND_UP) - increment
