#! /usr/bin/python

from csv import DictWriter
from os.path import join, basename
from os import listdir
from re import split
from operator import mul

work_dir="/home/jack/work/simulator/logs/4x4/"
keys = [
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

'planner_called', 
'end_simulation_time', 
'total_time_planning', 
'time_waiting_for_actions_to_finish', 
'time_waiting_for_planner_to_finish', 
]

def run(out_file="/home/jack/Desktop/test.csv"):
	
	with open(out_file, "w") as f:
		out = DictWriter(f, keys)
		out.writeheader()
		for name in (x for x in listdir(work_dir) if x.endswith(".log")):
			data = get_data(join(work_dir, name))
			out.writerow(data)
	
def get_data(name):

	with open(name) as f:
		try:
			data = eval(f.read())
		except:
			import pdb; pdb.set_trace()
			raise

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
			
	data["wait"] = (name[-1] == "-wait")
	return data

if __name__ == "__main__":
	run()


