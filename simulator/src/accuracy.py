from decimal import Decimal, ROUND_DOWN, ROUND_CEILING

__all__ = ["increment", "quantize", "as_end_time", "as_start_time", "to_prev_start_time"]

one = Decimal("1")

precision = Decimal("0")

increment = Decimal("0.5")

INSTANTANEOUS_ACTION_DURATION = increment


def quantize(value) -> Decimal:
    return Decimal(value).quantize(precision, rounding=ROUND_DOWN)


def to_prev_start_time(value: Decimal) -> Decimal:
    return as_start_time(value) - one


def as_start_time(value: Decimal) -> Decimal:
    return value.quantize(precision, rounding=ROUND_CEILING)


def as_end_time(value: Decimal) -> Decimal:
    if value.is_infinite():
        return value
    return value.quantize(precision, rounding=ROUND_CEILING) - increment
