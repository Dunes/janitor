import logging

from math import isnan

from planner import Planner
from logger import StyleAdapter
from collections import Iterable, namedtuple
from queue import PriorityQueue
from itertools import chain
from copy import deepcopy
from decimal import Decimal

from action import Move, Observe, Plan, ExtraClean, Stalled
from planning_exceptions import ExecutionError
from plan_action import ActionState, ExecutionState
from pddl_parser import _unknown_value_getter

log = StyleAdapter(logging.getLogger(__name__))

ExecutionResult = namedtuple("ExecutionResult", "executed_actions observations simulation_time")

def run_simulation(model, logger, planning_time):

	planner = Planner(planning_time)
	if isnan(planning_time):
		planning_time = 0

	# variables to run simulation
	simulation_time = 0
	new_knowledge = True
	planning_start = 0
	observation_whilst_planning = False
	predicted_model = None

	# variables used to record simulation
	planner_called = 0
	time_planning = 0
	time_waiting_for_actions_to_finish = 0
	time_waiting_for_planner_to_finish = 0
	executed = []

	# initial observations
	observe_environment(model)

	while new_knowledge and not is_goal_in_model(model["goal"], model):

		log.info("planning")
		if not observation_whilst_planning:
			plan, time_taken = planner.get_plan_and_time_taken(model)
		else:
			log.info("observation whilst planning, using predicted model")
			plan, time_taken = planner.get_plan_and_time_taken(predicted_model)
		logger.log_plan(plan)
		time_planning += time_taken
		planner_called += 1
		executed.append(Plan(planning_start, time_taken))
		if observation_whilst_planning: executed[-1].partial = True

		planning_finished = time_taken + planning_start
		if simulation_time > planning_finished:
			time_waiting_for_actions_to_finish += simulation_time - planning_finished
		else:
			time_waiting_for_planner_to_finish += planning_finished - simulation_time
		log.info("simulation_time {}", simulation_time)
		log.info("planning_finished {}", planning_finished)

		simulation_time = max(simulation_time, planning_finished)

		observers = observe_environment(model)
		if observers:
			raise ExecutionError("model in inconsistent state -- should be no possible observations")

		log.info("executing new plan")
		plan = adjust_plan(plan, simulation_time)
		model_hypothesis = get_model_hypothesis(model)
		pre_run_plan_simulation_time = simulation_time
		result = run_plan(model, plan, simulation_time, planning_time,
						flawed_plan=observation_whilst_planning)

		simulation_time = result.simulation_time
		if observation_whilst_planning:
			planning_start = pre_run_plan_simulation_time
		elif result.observations:
			planning_start = min(result.observations)
		else:
			log.warning("no observations in run and no observations whilst planning -- goal should be achieved")
			planning_start = False
			new_knowledge = False
		observation_whilst_planning = any(obs > planning_start for obs in result.observations)
		if observation_whilst_planning:
			predicted_model = predict_model(plan, model_hypothesis, simulation_time)
		executed.extend(result.executed_actions)


	log.info("simulation finished")

	goal_achieved = is_goal_in_model(model["goal"], model)
	log.info("Goal achieved: {}", goal_achieved)
	log.info("Planner called: {}", planner_called)
	log.info("Total time taken: {}", simulation_time)
	log.info("Time spent planning: {}", time_planning)
	log.info("time_waiting_for_actions_to_finish {}", time_waiting_for_actions_to_finish)
	log.info("time_waiting_for_planner_to_finish {}", time_waiting_for_planner_to_finish)

	logger.log_property("goal_achieved", goal_achieved)
	logger.log_property("planner_called", planner_called)
	logger.log_property("end_simulation_time", simulation_time)
	logger.log_property("total_time_planning", time_planning)
	logger.log_property("time_waiting_for_actions_to_finish", time_waiting_for_actions_to_finish)
	logger.log_property("time_waiting_for_planner_to_finish", time_waiting_for_planner_to_finish)
	executed_str = "'[{}]'".format(", ".join(str(action) for action in executed if type(action) is not Observe))
	logger.log_property("execution", executed_str)

	log.info("remaining temp nodes: {}",
		[(name, node) for name, node in model["nodes"].items() if name.startswith("temp")])

def agents(action):
	if type(action) is ExtraClean:
		return set((action.agent0, action.agent1))
	return set((action.agent,))


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
	return tuple(_adjust_plan_helper(plan, start_time))

def _adjust_plan_helper(plan, start_time):
	for action in plan:
		# adjust for OPTIC starting at t = 0
		action.start_time = action.start_time + start_time
		yield action
		if type(action) is Move:
			yield Observe(action.end_time, action.agent, action.end_node)

def predict_model(plan, model, deadline):
	log.debug("predict_model() deadline={}", deadline)
	execution_queue = PriorityQueue()
	for action in plan:
		if type(action) is not Observe:
			execution_queue.put(ActionState(action))

	execute_action_queue(model, execution_queue, break_on_new_knowledge=False, deadline=deadline)
	execute_partial_actions(get_executing_actions(execution_queue.queue, deadline), model, deadline)
#	remove_unused_temp_nodes(model)

	return model


def get_executing_actions(action_states, deadline):
	return list(action_state.action for action_state in action_states
			if action_state.state == ExecutionState.executing
				and action_state.action.start_time < deadline)


def run_plan(model, plan, simulation_time, execution_extension, *, flawed_plan):
	log.debug("run_plan() flawed_plan={}", flawed_plan)
	execution_queue = PriorityQueue()
	for action in plan:
		execution_queue.put(ActionState(action))


	if not flawed_plan:
		# execute main plan
		_result = execute_action_queue(model, execution_queue, break_on_new_knowledge=True, deadline=Decimal("infinity"))
		simulation_time, executed, observations, stalled = _result
	else:
		executed = []
		stalled = {}
		observations = set()

	if execution_queue.empty():
		return ExecutionResult(executed, (), simulation_time)

	observation_time = simulation_time

	# execute actions during replan phase
	deadline = observation_time + execution_extension
	_result = execute_action_queue(model, execution_queue, break_on_new_knowledge=False,
			deadline=deadline, stalled=stalled)
	_sim_time, additional_executed, observations2, stalled = _result

	# add stalled actions
	stalled_actions = list(Stalled(stalled_time, deadline-stalled_time, agent_name)
			for agent_name, stalled_time in stalled.items())

	# attempt to partially execute actions in mid-execution
	mid_executing_actions = get_executing_actions(execution_queue.queue, deadline)

	# mid execution action with zero duration is a bug
	assert not any(action for _t, state, action in execution_queue.queue
			if state == ExecutionState.executing and action.duration == 0)

	half_executed_actions = execute_partial_actions(mid_executing_actions, model, deadline)
#	remove_unused_temp_nodes(model)

	executed = executed + additional_executed + half_executed_actions + stalled_actions
	observations = observations | observations2
	simulation_time = max(a.end_time for a in executed)

	return ExecutionResult(executed, observations, simulation_time)


def execute_action_queue(model, execution_queue, *, break_on_new_knowledge=True, deadline, stalled=None):
	log.debug("execute_action_queue() break={}, deadline={}", break_on_new_knowledge, deadline)
	simulation_time = None
	executed = []
	observations = set()
	if stalled is None:
		stalled = {}

	while not execution_queue.empty():
		action_state = execution_queue.get()
		if action_state.time > deadline:
			execution_queue.put(action_state)
			break
		if agents(action_state.action).intersection(stalled):
			continue

		time, state, action = action_state
		simulation_time = time
		if state == ExecutionState.executing:
			action_state.finish()
			new_knowledge = action.apply(model)
			executed.append(action)
			if new_knowledge:
				observations.add(action.end_time)
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
			stalled.update((agent, action.start_time) for agent in agents(action))
		elif state == ExecutionState.pre_start:
			action_state.start()
			execution_queue.put(action_state)
		else:
			raise ExecutionError("action in unknown state")

	return simulation_time, executed, observations, stalled

def execute_partial_actions(mid_execution_actions, model, deadline):
	log.debug("execute_partial_actions() deadline={}", deadline)
	genr = (action.partially_apply(model, deadline)
		for action in mid_execution_actions)

	result = [a for a in genr if a]
	for a in result:
		log.info("partial: {}", a)
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

def get_model_hypothesis(model):
	model = deepcopy(model)
	assumed_values = model["assumed-values"]
	for node in model["nodes"].values():
		if "known" in node:
			node["known"].update({
				key: _unknown_value_getter(value, key, assumed_values)
				for key, value in node["unknown"].items()
			})
			node["unknown"].clear()
	return model