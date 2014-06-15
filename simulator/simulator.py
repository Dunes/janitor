#! /usr/bin/env python

import argparse
from math import isnan

from planner import Planner
import problem_parser
from logger import Logger

from operator import attrgetter
from collections import Iterable, namedtuple
from Queue import PriorityQueue
from math import isinf
from itertools import chain

from action import Clean, Move, ExecutionState, Observe, Plan, ExtraClean
from planning_exceptions import NoPlanException, StateException, ExecutionError

ExecutionResult = namedtuple("ExecutionResult", "executed_actions observation_time observation_whilst_planning")

def run_simulation(model, logger, planning_time):

	planner = Planner(planning_time)
	if isnan(planning_time):
		planning_time = 0

	# variables to run simulation
	simulation_time = 0
	new_knowledge = True
	observation_time = None
	
	# variables used to record simulation
	planner_called = 0
	time_planning = 0
	time_waiting_for_actions_to_finish = 0
	time_waiting_for_planner_to_finish = 0
	executed = []
	
	# initial observations
	observe_environment(model)
	
	while new_knowledge and not is_goal_in_model(model["goal"], model):
		
		plan, time_taken = planner.get_plan_and_time_taken(model)
		logger.log_plan(plan)
		time_planning += time_taken
		planner_called += 1
		executed.append(Plan((observation_time if observation_time is not None else simulation_time), time_taken))

		planning_finished = time_taken + (observation_time if observation_time is not None else simulation_time)
		if simulation_time > planning_finished:
			time_waiting_for_actions_to_finish += simulation_time - planning_finished
		else:
			time_waiting_for_planner_to_finish += planning_finished - simulation_time
		print "simulation_time", simulation_time
		print "planning_finished", planning_finished
		
		simulation_time = max(simulation_time, planning_finished)
		observation_time = None
		
		print "new plan"
		# observe environment and check for changes since planning, before executing plan
		observers = observe_environment(model)
		if observers:
			# plan invalid due to observations whilst planning, replan
			new_knowledge = True
			continue
		
		plan = adjust_plan(plan, simulation_time)
		result = run_plan(model, plan, planning_time)
		
		observation_time = result.observation_time
		simulation_time = result.observation_whilst_planning if result.observation_whilst_planning else observation_time
		new_knowledge = bool(observation_time)
		executed.extend(result.executed_actions)

	print "simulation finished"
	
	goal_achieved = is_goal_in_model(model["goal"], model)
	print "Goal achieved:", goal_achieved
	print "Planner called:", planner_called
	print "Total time taken:", simulation_time
	print "Time spent planning:", time_planning
	print "time_waiting_for_actions_to_finish", time_waiting_for_actions_to_finish
	print "time_waiting_for_planner_to_finish", time_waiting_for_planner_to_finish
	
	logger.log_property("goal_achieved", goal_achieved)
	logger.log_property("planner_called", planner_called)
	logger.log_property("end_simulation_time", simulation_time)
	logger.log_property("total_time_planning", time_planning)
	logger.log_property("time_waiting_for_actions_to_finish", time_waiting_for_actions_to_finish)
	logger.log_property("time_waiting_for_planner_to_finish", time_waiting_for_planner_to_finish)
	logger.log_property("execution", str([action for action in executed if type(action) is not Observe]))

def agents(action):
	if type(action) is ExtraClean:
		return set((action.agent0, action.agent1))
	return set((action.agent,))

def get_latest_observation_time(observers, executed):
	for action in sorted(executed, key=attrgetter("end_time"), reverse=True):
		if type(action) is Move and action.agent in observers and observers[action.agent] == action.end_node:
			return action.end_time
	return None

def observe_environment(model):
	# create Observe action for each agent
	actions = [Observe(None, agent_name, agent["at"][1])
			for agent_name, agent in model["agents"].items()] # could be generator rather than list
	# apply observation and collect those agents that observed something new
	return dict(
		(action.agent, action.node) for action in actions if action.apply(model)
	)

def adjust_plan(plan, start_time):
	plan = list(_adjust_plan_helper(plan))
	for action in plan:
		# adjust for OPTIC starting at t = 0
		action.start_time += start_time
	return plan

def _adjust_plan_helper(plan):
	for action in plan:
		yield action
		if type(action) is Move:
			yield Observe(action.end_time, action.agent, action.end_node)

def run_plan(model, plan, execution_extension):
	
	execution_queue = PriorityQueue()
	for action in plan:
		execution_queue.put((action.start_time, action.execution_state, action))
		
	_result = execute_action_queue(model, execution_queue, break_on_new_knowledge=True, deadline=float("infinity"))
	observation_time, executed = _result
	
	if execution_queue.empty():
		return ExecutionResult(executed, observation_time, None)
		
	deadline = observation_time + execution_extension
	_result = execute_action_queue(model, execution_queue, break_on_new_knowledge=False, deadline=deadline)
	observation_whilst_planning, additional_executed = _result

	return ExecutionResult(executed + additional_executed, observation_time, observation_whilst_planning)
	

def execute_action_queue(model, execution_queue, break_on_new_knowledge, deadline):
	simulation_time = None
	executed = []
	stalled = set()

	while not execution_queue.empty():
		time, state, action = execution_queue.get()
		if time > deadline:
			execution_queue.put((time, state, action))
			break
		if agents(action).intersection(stalled):
			continue
			
		simulation_time = time
		if action.execution_state == ExecutionState.executing:
			action.finish()
			new_knowledge = action.apply(model)
			executed.append(action)
			if break_on_new_knowledge and new_knowledge:
				# allow other concurrently finishing actions to finish rather than immediate break
				deadline = time
		elif not action.is_applicable(model):
			# order is such that action gets rejected before it starts, but is not rechecked after it has been started
			if break_on_new_knowledge:
				print action
				import pdb; pdb.set_trace()
				raise ExecutionError("action expects model to be in different state")
			stalled.update(agents(action))
		elif action.execution_state == ExecutionState.pre_start:
			action.start()
			execution_queue.put((action.end_time, action.execution_state, action))
		else:
			raise ExecutionError("action in unknown state")
	
	return simulation_time, executed


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
	p.add_argument("--planning-time", "-t", type=float, default="nan")
	p.add_argument("--log-directory", "-l", default="logs")
	return p

if __name__ == "__main__":
	args = parser().parse_args()
	print args
	model = problem_parser.decode(args.problem_file)
	log_file_name = Logger.get_log_file_name(args.problem_file, args.planning_time)
	print "log:", log_file_name
	with Logger(log_file_name, args.log_directory) as logger:
		run_simulation(model, logger, args.planning_time)
	
