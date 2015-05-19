__author__ = 'jack'

from enum import Enum
from copy import copy, deepcopy
from accuracy import quantize, as_end_time, as_start_time
from pddl_parser import unknown_value_getter
from action import Plan, Observe, Move, Clean, ExtraClean, Stalled, GetExecutionHeuristic
from action_state import ActionState, ExecutionState
from planning_exceptions import ExecutionError
from logger import StyleAdapter, DummyLogger
from requests import Request

from collections import namedtuple, Iterable
from priority_queue import MultiActionStateQueue
from itertools import chain
from decimal import Decimal
from logging import getLogger

log = StyleAdapter(getLogger(__name__))


class ActionResult(namedtuple("ActionResult", "action time result")):

    def __str__(self):
        return "ActionResult(action={arg.action!s}, time={arg.time!s}, result={arg.result!s})".format(arg=self)


class ExecutionProblem(Enum):
    AgentStalled = 0
    ReachedDeadline = 1


class Simulator:

    ID_COUNTER = 0

    def __init__(self, model, executors, planner, plan_logger=None, time=quantize(0)):
        self.model = model
        self.executors = executors
        self.planner = planner
        self.plan_logger = plan_logger if plan_logger else DummyLogger()
        self.executed = []
        self.stalled = set()
        self.time = time
        self.start_time = self.time
        self.id = self.get_next_id()

    def copy_with(self, *, model=None, executors=None, planner=None, plan_logger=None, time=None):
        model = model if model else deepcopy(self.model)
        executors = executors if executors else [executor.copy() for executor in self.executors]
        planner = planner if planner else self.planner
        plan_logger = plan_logger if plan_logger else DummyLogger()
        time = time if time else self.time
        return Simulator(model=model, executors=executors, planner=planner, plan_logger=plan_logger,
            time=time)

    def run(self, *, deadline=Decimal("Infinity")):
        log.info("Simulator({}).run() deadline={}", self.id, deadline)
        deadline = as_end_time(deadline)
        if self.time > deadline:
            log.info("Simulator({}).run() finished as time ({}) >= deadline ({})", self.id, self.time, deadline)
            return

        for executor in self.executors:
            executor.deadline = deadline

        if not any(executor.has_goals for executor in self.executors):
            log.info("Simulator({}).run() finished as no-op", self.id)
            return

        while any(executor.has_goals for executor in self.executors):
            action_states = MultiActionStateQueue(executor.next_action() for executor in self.executors).get()
            self.process_action_states(action_states)

        log.info("Simulator({}).run() finished", self.id)
        return self.is_goal_in_model()

    def process_action_states(self, action_states):
        first = action_states[0]
        log.debug("Simulator({}).process_action_state() time={a.time}, state={a.state!s}, action_state={a_s}", self.id,
            a=first, a_s=action_states)

        self.time = first.time
        if first.state == ExecutionState.pre_start:
            self.start_actions(action_states)
        elif first.state == ExecutionState.executing:
            self.finish_actions(action_states)
        else:
            raise ExecutionError("first action_state is invalid {} for time {} with action {}"
                .format(first.state, first.time, first.action))

    def start_actions(self, action_states):
        plan_action_states = []
        for action_state in action_states:
            if isinstance(action_state.action, Plan):
                plan_action_states.append(action_state)
            elif not action_state.action.is_applicable(self.model):
                log.error("{} has stalled attempting: {}", action_state.action.agents(), action_state.action)
                self.stalled.update((a, action_state.time) for a in action_state.action.agents())
                # agents should never stall when they are in charge of replanning locally.
                raise ExecutionError("agent has stalled")
            else:
                for agent in action_state.action.agents():
                    self.executors[agent].notify_action_starting(action_state, self.model)

        for action_state in plan_action_states:
            for agent in action_state.action.agents():
                new_action_state = self.executors[agent].notify_action_starting(action_state, self.model)
                self.plan_logger.log_plan(new_action_state.action.plan)

    def finish_actions(self, action_states):
        for action_state in action_states:
            if not action_state.action.is_applicable(self.model):
                log.debug("{} has stalled attempting: {}", action_state.action.agents(), action_state.action)
                self.stalled.update((a, action_state.time) for a in action_state.action.agents())
                # agents should never stall when they are in charge of replanning locally.
                raise ExecutionError("agent has stalled")
            else:
                for agent in action_state.action.agents():
                    self.executors[agent].notify_action_finishing(action_state, self.model)

    def get_plan(self, duration=None):
        log.debug("Simulator({}).get_plan()", self.id)
        deadline = self.executor.current_plan_execution_limit
        simulator = self.copy_with(model=self.convert_to_hypothesis_model(self.model))
        simulator.run(deadline=deadline)
        predicted_model = simulator.model
        return self.planner.get_plan_and_time_taken(predicted_model, duration=duration)

    def convert_to_hypothesis_model(self, model):
        log.debug("Simulator({}).convert_to_hypothesis_model()", self.id)
        model = deepcopy(model)
        assumed_values = model["assumed-values"]
        for node in model["nodes"].values():
            if "known" in node:
                node["known"].update({
                    key: unknown_value_getter(value, key, assumed_values)
                    for key, value in node["unknown"].items()
                })
                node["unknown"].clear()
        return model

    def is_goal_in_model(self):
        hard_goals = list(tuple(g) for g in self.model["goal"]["hard-goals"])
        goal = hard_goals
        it = ((obj_name, value.get("known", value))
              for obj_name, value in chain(self.model["agents"].items(), self.model["nodes"].items()))
        for obj_name, values in it:
            for pred_name, args in values.items():
                g = self.cons_goal(pred_name, obj_name, args)
                if g in goal:
                    goal.remove(g)

        return not goal

    @staticmethod
    def cons_goal(pred_name, obj_name, args):
        return (pred_name,) + Simulator.substitute_obj_name(obj_name, args)

    @staticmethod
    def substitute_obj_name(obj_name, args):
        if isinstance(args, Iterable):
            return tuple(obj_name if a is True else a for a in args)
        else:
            return obj_name if args is True else args,

    def print_results(self, logger):
        goal_achieved = self.is_goal_in_model()
        plan_actions = [a for a in self.executed if type(a) is Plan]
        planner_called = len(plan_actions)
        time_planning = sum(a.duration for a in self.executed if type(a) is Plan)
        time_waiting_for_actions_to_finish = self.get_time_waiting_for_actions_to_finish()
        time_waiting_for_planner_to_finish = self.get_time_waiting_for_planner_to_finish()
        try:
            stalled_actions = [Stalled(time, min(p.end_time for p in plan_actions if p.end_time > time) - time, agent)
                           for agent, time in self.stalled]
        except ValueError as e:
            log.warning("stalled action collation failed with: {}", e)
            stalled_actions = []
        log.info("Goal achieved: {}", goal_achieved)
        log.info("Planner called: {}", planner_called)
        log.info("Total time taken: {}", self.time)
        log.info("Time spent planning: {}", time_planning)
        log.info("time_waiting_for_actions_to_finish {}", time_waiting_for_actions_to_finish)
        log.info("time_waiting_for_planner_to_finish {}", time_waiting_for_planner_to_finish)

        logger.log_property("goal_achieved", goal_achieved)
        logger.log_property("planner_called", planner_called)
        logger.log_property("end_simulation_time", self.time)
        logger.log_property("total_time_planning", time_planning)
        logger.log_property("time_waiting_for_actions_to_finish", time_waiting_for_actions_to_finish)
        logger.log_property("time_waiting_for_planner_to_finish", time_waiting_for_planner_to_finish)
        executed_str = "[{}]".format(", ".join(str(action) for action in (self.executed + stalled_actions)
            if type(action) is not Observe))
        logger.log_property("execution", executed_str, stringify=repr)

        log.info("remaining temp nodes: {}",
            [(name, node) for name, node in self.model["nodes"].items() if name.startswith("temp")])

        return goal_achieved

    def get_time_waiting_for_actions_to_finish(self):
        plan_actions = [a for a in self.executed if type(a) is Plan]
        real_actions = [a for a in self.executed if type(a) in (Move, Clean, ExtraClean)]

        total_time = 0
        for p in plan_actions:
            overlapping_actions = [a for a in real_actions if a.start_time < p.end_time <= a.end_time]
            if len(overlapping_actions) > 0:
                t = max(a.end_time - p.end_time for a in overlapping_actions)
                total_time += t

        return total_time

    def get_time_waiting_for_planner_to_finish(self):
        plan_actions = [a for a in self.executed if type(a) is Plan]
        real_actions = [a for a in self.executed if type(a) in (Move, Clean, ExtraClean)]

        total_time = 0
        for p in plan_actions:
            previous_actions = [p.end_time - a.end_time for a in real_actions if a.end_time <= p.end_time]
            if len(previous_actions) == 0:
                t = p.duration
            else:
                t = min(p.end_time - a.end_time for a in real_actions if a.end_time <= p.end_time)
            total_time += t

        return total_time

    @classmethod
    def get_next_id(cls):
        id_ = cls.ID_COUNTER
        cls.ID_COUNTER += 1
        return id_
