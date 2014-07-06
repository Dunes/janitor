from decimal import Decimal

precision = Decimal("0.000")

def quantize(value):
	return Decimal.from_float(value).quantize(precision)