#! /usr/bin/env python

import planner
import problem_parser

from collections import Iterable
from itertools import chain

from sys import argv

def run_simulation(problem_file="janitor-sample.json"):

	planner_called = 0

	print problem_file
	model = problem_parser.decode(problem_file)
	new_knowledge = True
	execution = []
	
	while new_knowledge:
	
		plan = planner.get_plan(model)
		planner_called += 1
		new_knowledge = False
	
		for action in plan:
			print "applying:", action
			new_knowledge = action.apply(model)
			execution.append(action)
			if new_knowledge:
				print "found new information: replanning"
				break
		
	print "simulation finished"

	print "Goal was:", model["goal"]
	print "Final state:\n", model
	
	goal_achieved = is_goal_in_model(model["goal"], model)
	print "Goal achieved:", goal_achieved
	
	print "Planner called:", planner_called
	print "Actual execution:\n", execution
	return goal_achieved

def is_goal_in_model(goal, model):
	goal = list(tuple(g) for g in goal)
	it = ((obj_name, value.get("known", value)) for obj_name, value in chain(model["agents"].iteritems(), model["nodes"].iteritems()))
	for obj_name, values in it:
		for pred_name, args in values.iteritems():
			g = cons_goal(pred_name, obj_name, args)
			if g in goal:
				goal.remove(g)
	
	return not goal
			
def cons_goal(pred_name, obj_name, args):
	return (pred_name,) + substitute_obj_name(obj_name, args)

def substitute_obj_name(obj_name, args):
	if isinstance(args, Iterable):
		return tuple(obj_name if a is True else a for a in args)
	else:
		return (obj_name if args is True else args,)

if __name__ == "__main__":
	if len(argv) > 1:
		run_simulation(argv[1])
	else:
		run_simulation()
