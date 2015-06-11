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
from itertools import chain, count
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

    ID_COUNTER = count()

    def __init__(self, model, executors, plan_logger=None, time=quantize(0)):
        self.model = model
        self.executors = executors
        self.plan_logger = plan_logger if plan_logger else DummyLogger()
        self.executed = []
        self.stalled = set()
        self.time = time
        self.start_time = self.time
        self.id = next(self.ID_COUNTER)

    def copy_with(self, *, model=None, executors=None, plan_logger=None, time=None):
        model = model if model else deepcopy(self.model)
        executors = executors if executors else [executor.copy() for executor in self.executors]
        plan_logger = plan_logger if plan_logger else DummyLogger()
        time = time if time else self.time
        return Simulator(model=model, executors=executors, plan_logger=plan_logger,
            time=time)

    def run(self, *, deadline=Decimal("Infinity")):
        log.info("Simulator({}).run() deadline={}", self.id, deadline)
        deadline = as_end_time(deadline)
        if self.time > deadline:
            log.info("Simulator({}).run() finished as time ({}) >= deadline ({})", self.id, self.time, deadline)
            return

        for executor in self.executors.values():
            executor.deadline = deadline

        if not any(executor.has_goals for executor in self.executors.values()):
            log.info("Simulator({}).run() finished as no-op", self.id)
            return

        while self.time <= deadline and any(executor.has_goals for executor in self.executors.values()):
            action_states = MultiActionStateQueue(
                executor.next_action(self.time) for executor in self.executors.values() if executor.has_goals
            ).get()
            self.process_action_states(action_states)

        assert not any(executor.has_goals for executor in self.executors.values())

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
                #self.stalled.update((a, action_state.time) for a in action_state.action.agents())
                # agents should never stall when they are in charge of replanning locally.
                raise ExecutionError("agent has stalled")
            else:
                for agent in action_state.action.agents():
                    self.executors[agent].notify_action_starting(action_state, self.model)

        # sort so central planner is last
        plan_action_states = sorted(plan_action_states, key=lambda as_: "planner" in as_.action.agents())
        for action_state in plan_action_states:
            for agent in action_state.action.agents():
                new_action_state = self.executors[agent].notify_action_starting(action_state, self.model)
                #self.plan_logger.log_plan(new_action_state.action.plan)

    def finish_actions(self, action_states):
        for action_state in action_states:
            if not action_state.action.is_applicable(self.model):
                log.error("{} has stalled attempting: {}", action_state.action.agents(), action_state.action)
                #self.stalled.update((a, action_state.time) for a in action_state.action.agents())
                # agents should never stall when they are in charge of replanning locally.
                raise ExecutionError("agent has stalled")
            else:
                for agent in action_state.action.agents():
                    self.executors[agent].notify_action_finishing(action_state, self.model)

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