#! /usr/bin/env python

import argparse
from math import isnan

from planner import Planner
import problem_parser
from logger import Logger

from operator import attrgetter
from collections import Iterable, namedtuple
from queue import PriorityQueue
from math import isinf
from itertools import chain
from decimal import Decimal

from action import Clean, Move, ExecutionState, Observe, Plan, ExtraClean
from planning_exceptions import NoPlanException, StateException, ExecutionError

ExecutionResult = namedtuple("ExecutionResult", "executed_actions planning_start simulation_time")

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

		print("planning")
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
		print("simulation_time", simulation_time)
		print("planning_finished", planning_finished)

		simulation_time = max(simulation_time, planning_finished)
		observation_time = None

		print("executing new plan")
		# observe environment and check for changes since planning, before executing plan
		observers = observe_environment(model)
		if observers:
			# plan invalid due to observations whilst planning, replan
			print("plan inconsistent with state, replanning")
			new_knowledge = True
			continue

		plan = adjust_plan(plan, simulation_time)
		result = run_plan(model, plan, planning_time)

		observation_time = result.planning_start
		simulation_time = result.simulation_time
		new_knowledge = bool(observation_time)
		executed.extend(result.executed_actions)

	print("simulation finished")

	goal_achieved = is_goal_in_model(model["goal"], model)
	print("Goal achieved:", goal_achieved)
	print("Planner called:", planner_called)
	print("Total time taken:", simulation_time)
	print("Time spent planning:", time_planning)
	print("time_waiting_for_actions_to_finish", time_waiting_for_actions_to_finish)
	print("time_waiting_for_planner_to_finish", time_waiting_for_planner_to_finish)

	logger.log_property("goal_achieved", goal_achieved)
	logger.log_property("planner_called", planner_called)
	logger.log_property("end_simulation_time", simulation_time)
	logger.log_property("total_time_planning", time_planning)
	logger.log_property("time_waiting_for_actions_to_finish", time_waiting_for_actions_to_finish)
	logger.log_property("time_waiting_for_planner_to_finish", time_waiting_for_planner_to_finish)
	executed_str = "'[{}]'".format(", ".join(str(action) for action in executed if type(action) is not Observe))
	logger.log_property("execution", executed_str)

	print("remaining temp nodes:",
		[(name, node) for name, node in model["nodes"].iteritems() if name.startswith("temp")])

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
	# create Observe action for each agent in model
	actions = [Observe(None, agent_name, agent["at"][1])
			for agent_name, agent in model["agents"].items()]
	# apply observation and collect those agents that observed something new
	return dict(
		(action.agent, action.node) for action in actions if action.apply(model)
	)

def remove_unused_temp_nodes(model):
	to_keep = set(state["at"][1] for state in model["agents"].values() if state["at"][1].startswith("temp"))

	model["nodes"] = dict((k,v) for k,v in model["nodes"].items() if not k.startswith("temp") or k in to_keep)
	model["graph"]["edges"] = [edge for edge in model["graph"]["edges"]
							if not edge[0].startswith("temp") or edge[0] in to_keep]

def adjust_plan(plan, start_time):
	return list(_adjust_plan_helper(plan, start_time))

def _adjust_plan_helper(plan, start_time):
	for action in plan:
		# adjust for OPTIC starting at t = 0
		action.start_time = action.start_time + start_time
		yield action
		if type(action) is Move:
			yield Observe(action.end_time, action.agent, action.end_node)

def run_plan(model, plan, execution_extension):

	execution_queue = PriorityQueue()
	for action in plan:
		execution_queue.put((action.start_time, action.execution_state, action))

	# execute main plan
	_result = execute_action_queue(model, execution_queue, break_on_new_knowledge=True, deadline=float("infinity"))
	observation_time, executed, stalled = _result

	if execution_queue.empty():
		return ExecutionResult(executed, observation_time, max(a.end_time for a in executed))

	# execute actions during replan phase
	deadline = observation_time + execution_extension
	_result = execute_action_queue(model, execution_queue, break_on_new_knowledge=False, deadline=deadline,
			execute_partial_actions=execute_partial_actions, stalled=stalled)
	observation_whilst_planning, additional_executed = _result[:2] # ignore simulation time. why?

	# attempt to partially execute actions in mid-execution
	mid_executing_actions = list(action for _t, state, action in execution_queue.queue if state == ExecutionState.executing)
	half_executed_actions = execute_partial_actions(mid_executing_actions, model, deadline)
	remove_unused_temp_nodes(model)

	executed = executed + additional_executed + half_executed_actions
	planning_start = observation_whilst_planning or observation_time
	simulation_time = max(a.end_time for a in executed)

	return ExecutionResult(executed, planning_start, simulation_time)


def execute_action_queue(model, execution_queue, break_on_new_knowledge, deadline, execute_partial_actions=False, stalled=None):
	simulation_time = None
	executed = []
	if stalled is None:
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
			if break_on_new_knowledge and time < deadline:
				# if no observations inconsistent with plan then this is an error
				# however, may be processing actions starting at deadline, so allow these to stall and not report error
				#import pdb; pdb.set_trace()
				raise ExecutionError("action expects model to be in different state -- {}".format(action))
			stalled.update(agents(action))
		elif action.execution_state == ExecutionState.pre_start:
			action.start()
			execution_queue.put((action.end_time, action.execution_state, action))
		else:
			raise ExecutionError("action in unknown state")

	return simulation_time, executed, stalled

def execute_partial_actions(mid_execution_actions, model, deadline):
	genr = (action.partially_apply(model, deadline)
		for action in mid_execution_actions)

	result = [a for a in genr if a]
	for a in result:
		print("partial:", a)
	return result

def is_goal_in_model(goal, model):
	hard_goals = goal["hard-goals"]
	hard_goals = list(tuple(g) for g in hard_goals)
	goal = hard_goals
	it = ((obj_name, value.get("known", value)) for obj_name, value in chain(model["agents"].items(), model["nodes"].items()))
	for obj_name, values in it:
		for pred_name, args in values.items():
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
	p.add_argument("--planning-time", "-t", type=Decimal, default="nan")
	p.add_argument("--log-directory", "-l", default="logs")
	return p

if __name__ == "__main__":
	args = parser().parse_args()
	print(args)
	model = problem_parser.decode(args.problem_file)
	log_file_name = Logger.get_log_file_name(args.problem_file, args.planning_time)
	print("log:", log_file_name)
	with Logger(log_file_name, args.log_directory) as logger:
		run_simulation(model, logger, args.planning_time)

