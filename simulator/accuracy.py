from decimal import Decimal

precision = Decimal("0.000")

def quantize(float_):
	return Decimal.from_float(float_).quantize(precision)
