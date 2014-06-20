#! /usr/bin/python

import argparse

from csv import DictWriter, writer
from os.path import join, basename, splitext
from os import listdir
from re import split
from operator import mul
from itertools import groupby
from functools import partial

independent_vars = (
'goal_achieved', 
'planning_time', 
'size', 
'total_nodes', 
'start', 
'agents', 
'edge', 
'wait', 
'dirt_type', 
'dirt_min', 
'dirt_max', 
'extra_dirt',
"id",
)

dependent_vars = (
'planner_called', 
'end_simulation_time', 
'total_time_planning', 
'time_waiting_for_actions_to_finish', 
'time_waiting_for_planner_to_finish', 
)


def run(out_file, input_dir):
	
	raw_data = sorted((
		get_data(join(input_dir, name))
		for name in (x for x in listdir(input_dir) if x.endswith(".log"))
	), key=data_key)
	
	aggregated_data = (
		indy_vars + aggregate_data(group)
			for (_key, indy_vars), group in groupby(raw_data, partial(data_key, include_id=False))
	)
	
	with open(out_file, "w") as f:
		out = DictWriter(f, independent_vars + dependent_vars)
		out.writeheader()
		out.writerows(raw_data)
	del out
	
	with open("-aggregate".join(splitext(out_file)), "w") as f:
		out = writer(f)
		out.writerow(independent_vars[:-1] + ("count",) + dependent_vars)
		out.writerows(aggregated_data)
		

def data_key(data, include_id=True):
	base_key = (
		data["wait"],
		float(data["planning_time"]),
		data["extra_dirt"],
		int(data["total_nodes"]),
		data["size"],
		int(data["edge"]),
		int(data["agents"]),
		int(data["dirt_max"]),
		int(data["dirt_min"]),
#		data["dirt_type"],
	)
	if include_id:
		return base_key + (int(data["id"]),)
	else:
		return base_key, tuple(data[key] for key in independent_vars if key != "id")

def aggregate_data(data):
	grouped_data = zip(*[[datum[key] for key in dependent_vars] for datum in data])
	result = (len(grouped_data[0]),) + tuple(sum(v)/float(len(v)) for v in grouped_data)
	return result

def get_data(name):

	with open(name) as f:
		data = eval(f.read())


	del data["execution"]
	
	name_data = split("[\(\)]", basename(name)[5:-4])
	
	for label, value in zip(name_data[::2], name_data[1::2]):
		label = label.strip("-")
		if label == "extra_dirt":
			value = float(value.strip("%")) / 100
			data[label] = value
		elif label == "size":
			data[label] = value
			data["total_nodes"] = reduce(mul, eval(value))
		elif label == "dirt":
			dirt_type, dirt_min, dirt_max = value.split(",")
			data["dirt_type"] = dirt_type
			data["dirt_min"] = float(dirt_min)
			data["dirt_max"] = float(dirt_max)
		else:
			data[label] = value
	
	data["wait"] = (name_data[-1] == "-wait")
	return data

def parser():
	p = argparse.ArgumentParser(description="Converts planning log files to csv format")
	p.add_argument("--output", "-o", required=True)
	p.add_argument("--input-dir", "-i", required=True)
	p.add_argument("--output-dir", "-d", default="/home/jack/Dropbox/work/results")
	return p

if __name__ == "__main__":
	args = parser().parse_args()
	output_file = join(args.output_dir, args.output)
	run(output_file, args.input_dir)

