#! /usr/bin/env python

import argparse

from planner import Planner
import problem_parser

from collections import Iterable
from itertools import chain

from action import Clean, Move

from math import isinf

def run_simulation(problem_file, planning_time="first"):

	planner = Planner(planning_time)

	time_planning = 0
	plan_start_time = 0
	simulation_time = 0

	planner_called = 0


	model = problem_parser.decode(problem_file)
	new_knowledge = True
	execution = []
	execute_actions_before = 0
	
	time_waiting_for_actions_to_finish = 0
	time_waiting_for_planner_to_finish = 0
	
	while new_knowledge:

		plan, time_taken = planner.get_plan_and_time_taken(model)
		
		time_delta = simulation_time - (time_taken + execute_actions_before)
		if time_delta > 0:
			time_waiting_for_actions_to_finish += time_delta
		else:
			time_waiting_for_planner_to_finish += -time_delta
		print "time_delta", time_delta
		
		simulation_time += max(simulation_time, execute_actions_before + time_taken)
		
		time_planning += time_taken
		print "new plan"
		
		planner_called += 1
		new_knowledge = False
	
		execute_actions_before = float("infinity")
		
		# adjust for planner starting at t = 0
		for action in plan: 
			action.start_time += simulation_time
		
		for action in plan:
			if action.start_time >= execute_actions_before:
				break
			print "applying:", action
			new_knowledge_this_action = action.apply(model)
			execution.append(action)
			simulation_time = max(simulation_time, action.end_time)
			if new_knowledge_this_action and not new_knowledge:
				print "found new information: replanning"
				execute_actions_before = action.end_time
				new_knowledge = True
		
	print "simulation finished"

	print "Goal was:", model["goal"]
	print "Final state:\n", model
	
	goal_achieved = is_goal_in_model(model["goal"], model)
	print "Goal achieved:", goal_achieved
	
	print "Planner called:", planner_called
	print "Actual execution:\n", execution
	print "Total time taken:", simulation_time
	print "Time spent planning:", time_planning
	print "time_waiting_for_actions_to_finish", time_waiting_for_actions_to_finish
	print "time_waiting_for_planner_to_finish", time_waiting_for_planner_to_finish

def is_goal_in_model(goal, model):
	hard_goals = goal["hard-goals"]
	hard_goals = list(tuple(g) for g in hard_goals)
	goal = hard_goals
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

def parser():
	p = argparse.ArgumentParser(description="Simulator to run planner and carry out plan")
	p.add_argument("problem_file", default="janitor-preferences-sample.json", nargs="?")
	p.add_argument("--planning_time", "-t", type=float, default='nan')
	return p

def print_args(problem_file, planning_time):
	print problem_file, planning_time

if __name__ == "__main__":
	args = parser().parse_args()
	print args
	run_simulation(**args.__dict__)
