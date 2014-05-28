#! /usr/bin/env python

import argparse
from collections import namedtuple
from json import dump
from copy import deepcopy
from itertools import chain
from action import Observe

from random import uniform as rand

class Point(namedtuple("Point","x y")):
	pass
	
class ActualMinMax(namedtuple("ActualMinMax","actual min max")):
	pass

class TupleAction(argparse.Action):

	def __init__(self, maintype, subtype, **kwargs):
		super(TupleAction, self).__init__(**kwargs)
		self.maintype = maintype
		self.subtype = subtype		
	
	def create(self, values):
		if isinstance(values, str):
			v = self.create_item(values)
		else:
			v = tuple(self.create_item(i) for i in values)
		return v
	
	def create_item(self, values):
		return self.maintype(*(self.subtype(i) for i in values.split(",")))

class ActualMinMaxAction(TupleAction):
	def __init__(self, **kwargs):
		super(ActualMinMaxAction, self).__init__(ActualMinMax, float, **kwargs)
	
	def __call__(self, parser, namespace, values, option_string=None):
		v = self.create(values)
		setattr(namespace, self.dest, v)

class PointAction(TupleAction):
	def __init__(self, **kwargs):
		super(PointAction, self).__init__(Point, int, **kwargs)

	def __call__(self, parser, namespace, values, option_string=None):
		v = self.create(values)
		setattr(namespace, self.dest, v)

def parser():
	p = argparse.ArgumentParser(description="Creates problems from parameters")
	p.add_argument("--output","-o", required=True)
	p.add_argument("--size", "-s", required=True, action=PointAction, help="the size of the map grid, specified as x,y")
	p.add_argument("--dirtiness","-d", required=True, action=ActualMinMaxAction)
	p.add_argument("--extra-dirty-rooms","-ed", required=False, nargs="*", action=PointAction)
	p.add_argument("--required-stock","-rs", required=True, action=ActualMinMaxAction)
	p.add_argument("--assume-clean", default=False)
	p.add_argument("--assume-stocked", default=False)
	p.add_argument("--resource-rooms", "-rr", nargs="+", action=PointAction, required=True)
	p.add_argument("--edge-length","-el", default=10, type=int)
	
	p.add_argument("--violation-weight","-vw", default=100, type=int)
	
	p.add_argument("--agents", "-a", required=True, type=int)
	p.add_argument("--agent-start","-as", required=True, action=PointAction)
	p.add_argument("--carry-capacity","-cc", required=True, action=ActualMinMaxAction)
	
	p.add_argument("--problem-name","-pn", required=True)
	p.add_argument("--domain","-dn", required=True)
	return p

def create_problem(output, size, dirtiness, required_stock, assume_clean, assume_stocked, resource_rooms, edge_length, violation_weight, agents, agent_start, carry_capacity, problem_name, domain, extra_dirty_rooms):
	assume_dirty = not assume_clean
	problem = {
		"problem": problem_name,
		"domain": domain,
		"assumed-values": {
		 	"dirty": assume_dirty,
		 	"cleaned": assume_clean,
		 	"dirtiness": ("max" if assume_dirty else 0),
		 	"under-stocked": not assume_stocked,
		 	"fully-stocked": assume_stocked,
		 	"req-stock": "max",
		 	"extra-dirty": False,
		 	"not-extra-dirty": True,
		 }
	}
	
	problem["nodes"] = create_nodes(size, resource_rooms, extra_dirty_rooms, dirtiness, required_stock)
	problem["graph"], grid = create_graph(size, resource_rooms, extra_dirty_rooms, edge_length)
	problem["agents"] = create_agents(agents, carry_capacity, grid[agent_start.x][agent_start.y])
	problem["goal"] = create_goal(size, resource_rooms, extra_dirty_rooms)
	problem["metric"] = create_metric(violation_weight, size, resource_rooms)
	
	# start problem such that agents have observed starting location
	for agent_name, agent in problem["agents"].items():
		rm = agent["at"][1]
		Observe(None, agent_name, rm).apply(problem)
	
	with open(output, "w") as f:
		dump(problem, f)

def create_nodes(size, resource_rooms, extra_dirty_rooms, dirtiness, req_stock):
	num_resource_rooms = len(resource_rooms)
	num_extra_dirty_rooms = len(extra_dirty_rooms)
	total_normal_rooms = size.x * size.y - num_resource_rooms - num_extra_dirty_rooms
	
	if set(resource_rooms).intersection(extra_dirty_rooms):
		raise Exception("rooms cannot be both resource rooms and extra dirty: "+str(set(resource_rooms).intersection(extra_dirty_rooms)))
	
	resource_rms = (
		("res-rm"+str(i), {"node": True, "is-resource-room": True}) 
			for i in range(1, num_resource_rooms+1)
	)
	
#	extra_dirty_room = create_room(dirtiness, req_stock, extra_dirty=True)
	
	extra_dirty_rms = (
		("rm-ed"+str(i), create_room(dirtiness, req_stock, extra_dirty=True)) for i in range(1, num_extra_dirty_rooms + 1)
	)
	
#	room = create_room(dirtiness, req_stock, extra_dirty=False)
	
	rooms = (
		("rm"+str(i), create_room(dirtiness, req_stock, extra_dirty=False)) for i in range(1, total_normal_rooms + 1)
	)
	
	return dict(chain(resource_rms, rooms, extra_dirty_rms))


def create_graph(size, resource_rooms, extra_dirty_rooms, edge_length):
	num_resource_rooms = len(resource_rooms)
	total_rooms = size.x * size.y - num_resource_rooms
	res_room_num = 1
	extra_dirty_room_num = 1
	room_num = 1
	
	grid = []
	for x in range(size.x):
		column = []
		for y in range(size.y):
			 if (x,y) in resource_rooms:
			 	column.append("res-rm"+str(res_room_num))
			 	res_room_num += 1
			 elif (x,y) in extra_dirty_rooms:
			 	column.append("rm-ed"+str(extra_dirty_room_num))
			 	extra_dirty_room_num += 1
			 else:
			 	column.append("rm"+str(room_num))
			 	room_num += 1
		grid.append(column)
		
	edges = []
	for x, column in enumerate(grid):
		for y, room in enumerate(column):
			if x - 1 >= 0:
				edges.append([room, grid[x-1][y],edge_length])
			if x + 1 < size.x:
				edges.append([room, grid[x+1][y],edge_length])
			if y - 1 >= 0:
				edges.append([room, grid[x][y-1],edge_length])
			if y + 1 < size.y:
				edges.append([room, grid[x][y+1],edge_length])			
	
	return ({
		"bidirectional": False,
		"edges": edges
	}, grid)
	
def create_agents(agents, carry_capacity, room):
	agent = create_agent(carry_capacity, room)
 	return dict(
 		("agent"+str(i), deepcopy(agent))
 			for i in range(1, agents+1)
 	)	

def create_agent(carry_capacity, room):
	return {"agent": True,
 		"available": True,
 		"at": [True, room],
 		"carrying": carry_capacity.actual,
 		"max-carry": carry_capacity.max
 	}
	
def create_goal(size, resource_rooms, extra_dirty_rooms):
	num_rooms = (size.x * size.y) - len(resource_rooms) - len(extra_dirty_rooms)
	room_ids = chain(
		("rm"+str(i) for i in range(1, num_rooms+1)),
		("rm-ed"+str(i) for i in range(1, len(extra_dirty_rooms)+1))
	)
	return {
		"hard-goals": [
			["cleaned", rm_id] for rm_id in room_ids
		]
	}
	
def create_metric(violation_weight, size, resource_rooms):
	num_rooms = (size.x * size.y) - len(resource_rooms)
	return {"type": "minimize",
		"predicate": ["total-time"]
#	 	"predicate": ["+", ["total-time"]] + [
#		 	["*", violation_weight, ["is-violated", "stocked-rm"+str(i)]]
#		 		for i in range(1, num_rooms+1)
#		]
 	}

def create_room(dirtiness, req_stock, extra_dirty):
	return {
		"known": {
	 		"node": True,
	 		"is-room": True
	 	},
	 	"unknown": {
	 		"extra-dirty": {
	 			"actual": extra_dirty
	 		},
	 		"not-extra-dirty": {
	 			"actual": not extra_dirty
	 		},
	 		"dirtiness": {
	 			"min": dirtiness.min,
	 			"max": dirtiness.max,
	 			"actual": (dirtiness.actual if dirtiness.actual != "random" else rand(dirtiness.min, dirtiness.max))
	 		},
	 		"dirty": {
	 			"actual": dirtiness.actual > 0
	 		},
	 		"cleaned": {
	 			"actual": dirtiness.actual == 0
	 		},
	 		"req-stock": {
	 			"min": req_stock.min,
	 			"max": req_stock.max,
	 			"actual": req_stock.actual
	 		},
	 		"under-stocked": {
	 			"actual": req_stock.actual > 0
	 		},
	 		"fully-stocked": {
	 			"actual": req_stock.actual == 0
	 		}
		}
	}

if __name__ == "__main__":
	args = parser().parse_args()
	print args
	create_problem(**args.__dict__)
