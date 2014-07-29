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
from action_state import ActionState, ExecutionState
from pddl_parser import _unknown_value_getter


log = StyleAdapter(logging.getLogger(__name__))

ExecutionResult = namedtuple("ExecutionResult", "executed observations simulation_time")


class Simulator:

    def __init__(self, model, logger, planning_time):
        self.model = model
        self.logger = logger
        self.planner = Planner(planning_time)
        if isnan(planning_time):
            planning_time = 0
        self.planning_time = planning_time

    def run(self):
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
        self.observe_environment(self.model)

        while new_knowledge and not self.is_goal_in_model():

            log.info("planning")
            if not observation_whilst_planning:
                plan, time_taken = self.planner.get_plan_and_time_taken(self.model)
            else:
                log.info("observation whilst planning, using predicted model")
                plan, time_taken = self.planner.get_plan_and_time_taken(predicted_model)
            self.logger.log_plan(plan)
            time_planning += time_taken
            planner_called += 1
            executed.append(Plan(planning_start, time_taken))
            if observation_whilst_planning:
                executed[-1].partial = True

            planning_finished = time_taken + planning_start
            if simulation_time > planning_finished:
                time_waiting_for_actions_to_finish += simulation_time - planning_finished
            else:
                time_waiting_for_planner_to_finish += planning_finished - simulation_time
            log.info("simulation_time {}", simulation_time)
            log.info("planning_finished {}", planning_finished)

            simulation_time = max(simulation_time, planning_finished)

            observers = self.observe_environment(self.model)
            if observers:
                raise ExecutionError("model in inconsistent state -- should be no possible observations")

            log.info("executing new plan")
            plan = self.adjust_plan(plan, simulation_time)
            original_model = deepcopy(self.model)
            pre_run_plan_simulation_time = simulation_time
            result = self.run_plan(self.model, plan, simulation_time, self.planning_time,
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
                predicted_model = self.predict_model(plan, original_model, simulation_time-self.planning_time,
                    simulation_time)
            executed.extend(result.executed)

        log.info("simulation finished")

        goal_achieved = self.is_goal_in_model()
        log.info("Goal achieved: {}", goal_achieved)
        log.info("Planner called: {}", planner_called)
        log.info("Total time taken: {}", simulation_time)
        log.info("Time spent planning: {}", time_planning)
        log.info("time_waiting_for_actions_to_finish {}", time_waiting_for_actions_to_finish)
        log.info("time_waiting_for_planner_to_finish {}", time_waiting_for_planner_to_finish)

        self.logger.log_property("goal_achieved", goal_achieved)
        self.logger.log_property("planner_called", planner_called)
        self.logger.log_property("end_simulation_time", simulation_time)
        self.logger.log_property("total_time_planning", time_planning)
        self.logger.log_property("time_waiting_for_actions_to_finish", time_waiting_for_actions_to_finish)
        self.logger.log_property("time_waiting_for_planner_to_finish", time_waiting_for_planner_to_finish)
        executed_str = "[{}]".format(", ".join(str(action) for action in executed if type(action) is not Observe))
        self.logger.log_property("execution", executed_str, stringify=repr)

        log.info("remaining temp nodes: {}",
            [(name, node) for name, node in self.model["nodes"].items() if name.startswith("temp")])

        return goal_achieved

    @staticmethod
    def agents(action) -> set:
        if type(action) is ExtraClean:
            return {action.agent0, action.agent1}
        return {action.agent}

    @staticmethod
    def observe_environment(model):
        # create Observe action for each agent in model
        actions = [Observe(None, agent_name, agent["at"][1])
                for agent_name, agent in model["agents"].items()]
        # apply observation and collect those agents that observed something new
        return dict(
            (action.agent, action.node) for action in actions if action.apply(model)
        )

    def adjust_plan(self, plan, start_time):
        return tuple(self._adjust_plan_helper(plan, start_time))

    @staticmethod
    def _adjust_plan_helper(plan, start_time):
        for action in plan:
            # adjust for OPTIC starting at t = 0
            action.start_time = action.start_time + start_time
            yield action
            if type(action) is Move:
                yield Observe(action.end_time, action.agent, action.end_node)

    def predict_model(self, plan, model, first_observation, planning_finished):
        log.debug("predict_model() first_observation={}, planning_finished={}", first_observation, planning_finished)
        execution_queue = PriorityQueue()
        for action in plan:
            if type(action) is not Observe or action.end_time <= first_observation:
                execution_queue.put(ActionState(action))

        _result, stalled = self.execute_action_queue(model, execution_queue,
                break_on_new_knowledge=True, deadline=first_observation)

        model_hypothesis = self.convert_to_hypothesis_model(model)

        result, stalled = self.execute_action_queue(model_hypothesis, execution_queue,
                break_on_new_knowledge=False, deadline=planning_finished, stalled=stalled)

        assert result.observations == set()

        self.execute_partial_actions(self.get_executing_actions(execution_queue.queue, planning_finished),
                model_hypothesis, planning_finished)

        return model_hypothesis

    @staticmethod
    def get_executing_actions(action_states, deadline):
        return list(action_state.action for action_state in action_states
                if action_state.state == ExecutionState.executing
                    and action_state.action.start_time < deadline)

    def run_plan(self, model, plan, simulation_time, execution_extension, *, flawed_plan=False):
        log.debug("run_plan() flawed_plan={}", flawed_plan)
        execution_queue = PriorityQueue()
        for action in plan:
            execution_queue.put(ActionState(action))

        if not flawed_plan:
            # execute main plan
            result1, stalled = self.execute_action_queue(model, execution_queue,
                                    break_on_new_knowledge=True, deadline=Decimal("infinity"))
            simulation_time = result1.simulation_time
        else:
            result1 = ExecutionResult(executed=[], observations=set(), simulation_time=simulation_time)
            stalled = {}

        if execution_queue.empty():
            return result1

        self.post_observation_strategy()

        observation_time = simulation_time

        # execute actions during re-plan phase
        deadline = observation_time + execution_extension
        result2, stalled = self.execute_action_queue(model, execution_queue, break_on_new_knowledge=False,
                deadline=deadline, stalled=stalled)

        # add stalled actions
        stalled_actions = list(Stalled(stalled_time, deadline-stalled_time, agent_name)
                for agent_name, stalled_time in stalled.items())

        # attempt to partially execute actions in mid-execution
        mid_executing_actions = self.get_executing_actions(execution_queue.queue, deadline)

        # mid execution action with zero duration is a bug
        assert not any(action for _t, state, action in execution_queue.queue
                if state == ExecutionState.executing and action.duration == 0)

        half_executed_actions = self.execute_partial_actions(mid_executing_actions, model, deadline)

        executed = result1.executed + result2.executed + half_executed_actions + stalled_actions
        observations = result1.observations | result2.observations
        simulation_time = max(a.end_time for a in executed)

        return ExecutionResult(executed, observations, simulation_time)

    def execute_action_queue(self, model, execution_queue, *, break_on_new_knowledge=True, deadline, stalled=None):
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
            if self.agents(action_state.action).intersection(stalled):
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
                # order is such that action gets rejected before it starts, but is not rechecked after it has been
                # started
                if break_on_new_knowledge and time < deadline:
                    # if no observations inconsistent with plan then this is an error
                    # however, may be processing actions starting at deadline, so allow these to stall and not
                    # report error
                    #import pdb; pdb.set_trace()
                    raise ExecutionError("action expects model to be in different state -- {}".format(action))
                log.debug("{} has stalled", self.agents(action))
                stalled.update((agent, action.start_time) for agent in self.agents(action))
            elif state == ExecutionState.pre_start:
                action_state.start()
                execution_queue.put(action_state)
            else:
                raise ExecutionError("action in unknown state")

        return ExecutionResult(executed, observations, simulation_time), stalled

    @staticmethod
    def execute_partial_actions(mid_execution_actions, model, deadline):
        log.debug("execute_partial_actions() deadline={}", deadline)
        generator = (action.partially_apply(model, deadline)
            for action in mid_execution_actions)

        result = [a for a in generator if a]
        for a in result:
            log.info("partial: {}", a)
        return result

    def is_goal_in_model(self):
        hard_goals = self.model["goal"]["hard-goals"]
        hard_goals = list(tuple(g) for g in hard_goals)
        goal = hard_goals
        it = ((obj_name, value.get("known", value))
              for obj_name, value in chain(self.model["agents"].items(), self.model["nodes"].items()))
        for obj_name, values in it:
            for pred_name, args in values.items():
                g = self.cons_goal(pred_name, obj_name, args)
                if g in goal:
                    goal.remove(g)

        return not goal

    def cons_goal(self, pred_name, obj_name, args):
        return (pred_name,) + self.substitute_obj_name(obj_name, args)

    @staticmethod
    def substitute_obj_name(obj_name, args):
        if isinstance(args, Iterable):
            return tuple(obj_name if a is True else a for a in args)
        else:
            return obj_name if args is True else args,

    @staticmethod
    def convert_to_hypothesis_model(model):
        assumed_values = model["assumed-values"]
        for node in model["nodes"].values():
            if "known" in node:
                node["known"].update({
                    key: _unknown_value_getter(value, key, assumed_values)
                    for key, value in node["unknown"].items()
                })
                node["unknown"].clear()
        return model