import json
from decimal import Decimal

def decode(filename):
	with open(filename) as fh:
		obj = json.load(fh, parse_float=Decimal)
	return obj

def encode(filename, obj):
	with open(filename, mode="w") as fh:
		json.dump(obj, fh)
