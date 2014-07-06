from decimal import Decimal
from accuracy import precision

def quantize(value):
    if type(value) is float:
        return Decimal.from_float(value).quantize(precision)
    else:
        return Decimal(value).quantize(precision)