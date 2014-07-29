from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

precision = Decimal("0")

increment = Decimal("0.5")


def quantize(value):
    return Decimal(value).quantize(precision, rounding=ROUND_DOWN)


def round_half_up(value):
    return Decimal(value).quantize(precision, rounding=ROUND_HALF_UP)