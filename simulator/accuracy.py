from decimal import Decimal

precision = Decimal("0.000")

def quantize(float):
	return Decimal(float).quantize(precision)
