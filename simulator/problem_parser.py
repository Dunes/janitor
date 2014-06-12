import json

def decode(filename):
	with open(filename) as fh:
		obj = json.load(fh)	
	return obj

def encode(filename, obj):
	with open(filename, mode="w") as fh:
		json.dump(obj, fh)
