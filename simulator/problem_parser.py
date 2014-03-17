import json

def decode(filename):
	with open(filename) as fh:
		obj = json.load(fh)	
	return obj

def encode(filename):
	with open(filename, mode="w") as fh:
		obj = json.dump(fh)	
