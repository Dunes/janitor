from decimal import Decimal

precision = Decimal("0.000")

def quantize(float):
	return Decimal.from_float(float).quantize(precision)
