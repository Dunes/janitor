#! /usr/bin/python3

from accuracy import round_half_up
from simplejson import load, dump
from sys import stdin

for filename in stdin:
	with open(filename.strip()) as f:
		model = load(f, parse_float=round_half_up)
	with open(filename.strip(), "w") as f:
		dump(model, f)
