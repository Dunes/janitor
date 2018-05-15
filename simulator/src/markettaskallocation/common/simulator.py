from enum import Enum
from copy import deepcopy
from collections import namedtuple, Iterable, OrderedDict
from itertools import count
from decimal import Decimal
from logging import getLogger
from fractions import Fraction
from json import dump
from typing import Sequence

from accuracy import quantize, as_end_time, as_start_time
from markettaskallocation.common.action import Action, Plan, Observe, EventAction, Allocate
from markettaskallocation.common.domain_context import DomainContext
from action_state import ExecutionState
from planning_exceptions import ExecutionError
from logger import StyleAdapter, DummyLogger
from priority_queue import MultiActionStateQueue
from jsonencoder import ActionEncoder
from period import get_contiguous_periods

__author__ = 'jack'

log = StyleAdapter(getLogger(__name__))


class ActionResult(namedtuple("ActionResult", "action time result")):

    def __str__(self):
        return "ActionResult(action={arg.action!s}, time={arg.time!s}, result={arg.result!s})".format(arg=self)


class ExecutionProblem(Enum):
    AgentStalled = 0
    ReachedDeadline = 1


class Simulator:

    ID_COUNTER = count()

    def __init__(self, model, executors, plan_logger=None, time=quantize(0), *, real_actions: Sequence[Action],
                 domain_context: DomainContext):
        self.model = model
        self.executors = executors
        self.plan_logger = plan_logger if plan_logger else DummyLogger()
        self.executed = []
        self.stalled = set()
        self.time = time
        self.start_time = self.time
        self.real_actions = tuple(real_actions)
        self.id = next(self.ID_COUNTER)
        self.domain_context = domain_context

    def copy_with(self, *, model=None, executors=None, plan_logger=None, time=None):
        model = model if model else deepcopy(self.model)
        executors = executors if executors else [executor.copy() for executor in self.executors]
        plan_logger = plan_logger if plan_logger else DummyLogger()
        time = time if time else self.time
        return Simulator(
            model=model, executors=executors, plan_logger=plan_logger, time=time, real_actions=self.real_actions,
            domain_context=self.domain_context,
        )

    def run(self, *, deadline=Decimal("Infinity")):
        log.info("Simulator({}).run() deadline={}", self.id, deadline)
        deadline = as_end_time(deadline)
        if self.time > deadline:
            log.info("Simulator({}).run() finished as time ({}) >= deadline ({})", self.id, self.time, deadline)
            return

        for executor in self.executors.values():
            # executor.deadline = deadline
            pass

        if not any(e.has_goals for e in self.executors.values()):
            log.info("Simulator({}).run() finished as no-op", self.id)
            return

        while self.time <= deadline and any(e.has_goals for e in self.executors.values()):
            queue = MultiActionStateQueue(
                e.next_action(self.time) for e in self.executors.values() if e.has_goals
            )
            action_states = queue.get()
            self.process_action_states(action_states)

        assert not any(e.has_goals for e in self.executors.values())

        log.info("Simulator({}).run() finished", self.id)
        return self.is_goal_in_model()

    def process_action_states(self, action_states):
        first = action_states[0]
        log.debug("Simulator({}).process_action_state() time={a.time}, state={a.state!s}, action_state={a_s}", self.id,
            a=first, a_s=action_states)

        if self.time > as_start_time(first.time):
            raise ValueError("action with start time in the past " + str(first.action))
        self.time = first.time
        if first.state == ExecutionState.pre_start:
            self.start_actions(action_states)
        elif first.state == ExecutionState.executing:
            self.finish_actions(action_states)
            self.executed.extend(action_state.action for action_state in action_states)
        else:
            raise ExecutionError("first action_state is invalid {} for time {} with action {}"
                .format(first.state, first.time, first.action))

    def start_actions(self, action_states):
        plan_action_states = []
        for action_state in action_states:
            if isinstance(action_state.action, Plan):
                plan_action_states.append(action_state)
            elif not action_state.action.is_applicable(self.model):
                log.error("{} has stalled attempting: {}", action_state.action.agent, action_state.action)
                log.error("agent state: {}", self.domain_context.get_agent(self.model, action_state.action.agent))
                if hasattr(action_state.action, "room"):
                    log.error("room state: {}", self.domain_context.get_node(self.model, action_state.action.room))
                # agents should never stall when they are in charge of replanning locally.
                raise ExecutionError("agent has stalled")
            else:
                agent = action_state.action.agent
                self.executors[agent].notify_action_starting(action_state, self.model)

        # sort so central planner is last
        plan_action_states = sorted(plan_action_states, key=lambda as_: "planner" == as_.action.agent)
        for action_state in plan_action_states:
            agent = action_state.action.agent
            new_action_state = self.executors[agent].notify_action_starting(action_state, self.model)
            # self.plan_logger.log_plan(new_action_state.action.plan)

    def finish_actions(self, action_states):
        for action_state in action_states:
            if not action_state.action.is_applicable(self.model):
                log.error("{} has stalled attempting: {}", action_state.action.agent, action_state.action)
                # agents should never stall when they are in charge of replanning locally.
                raise ExecutionError("agent has stalled")
            else:
                agent = action_state.action.agent
                self.executors[agent].notify_action_finishing(action_state, self.model)

    def is_goal_in_model(self):
        goals = self.model["goal"][self.domain_context.goal_key]
        total_goals = len(goals)
        goal = list(tuple(g) for g in goals)
        for obj_type, objects in self.model["objects"].items():
            for obj_name, obj_value in objects.items():
                known_values = obj_value.get("known", obj_value)
                for predicate_name, args in known_values.items():
                    g = self.cons_goal(predicate_name, obj_name, args)
                    if g in goal:
                        goal.remove(g)
        failed_goals = len(goal)
        return 1 - Fraction(failed_goals, total_goals)

    def cons_goal(self, pred_name, obj_name, args):
        return (pred_name,) + self.substitute_obj_name(obj_name, args)

    @staticmethod
    def substitute_obj_name(obj_name, args):
        if isinstance(args, Iterable):
            return tuple(obj_name if a is True else a for a in args)
        else:
            return obj_name if args is True else args,

    def print_results(self, logger):
        goal_achieved = self.is_goal_in_model()
        allocation_actions = [a for a in self.executed if isinstance(a, Allocate)]
        plan_actions = [a for a in self.executed if isinstance(a, Plan)]

        time_taken = max((as_start_time(a.end_time) for a in self.executed if not isinstance(a, EventAction)),
                         default=0)
        time_allocating = sum(a.duration for a in allocation_actions)
        time_planning_total = sum(a.duration for a in plan_actions)
        time_planning_makespan = sum(p.duration for p in get_contiguous_periods(plan_actions))

        execution = [action for action in self.executed if type(action) is not Observe]

        data = OrderedDict((
            ("goal_achieved", float(goal_achieved)),
            ("end_simulation_time", time_taken),
            ("time_allocating", time_allocating),
            ("time_planning_total", time_planning_total),
            ("time_planning_makespan", time_planning_makespan),
            ("execution", execution),
        ))

        log.info("Goal achieved: {}", goal_achieved)
        log.info("Total time taken: {}", time_taken)
        log.info("Time spent allocating: {}", time_allocating)
        log.info("Total time spent planning: {}", time_planning_total)
        log.info("Makespan of time spent planning: {}", time_planning_makespan)

        with open(logger.log_file_name, "w") as f:
            dump(data, f, cls=ActionEncoder)

        log.info("remaining temp nodes: {}",
            [(name, node) for name, node in self.model["graph"]["edges"].items() if name.startswith("temp")])

        return goal_achieved

    def get_time_waiting_for_actions_to_finish(self):
        plan_actions = [a for a in self.executed if type(a) is Plan]
        real_actions = [a for a in self.executed if type(a) in self.real_actions]

        total_time = 0
        for p in plan_actions:
            overlapping_actions = [a for a in real_actions if a.start_time < p.end_time <= a.end_time]
            if len(overlapping_actions) > 0:
                t = max(a.end_time - p.end_time for a in overlapping_actions)
                total_time += t

        return total_time

    def get_time_waiting_for_planner_to_finish(self):
        plan_actions = [a for a in self.executed if type(a) is Plan]
        real_actions = [a for a in self.executed if type(a) in self.real_actions]

        total_time = 0
        for p in plan_actions:
            previous_actions = [p.end_time - a.end_time for a in real_actions if a.end_time <= p.end_time]
            if len(previous_actions) == 0:
                t = p.duration
            else:
                t = min(p.end_time - a.end_time for a in real_actions if a.end_time <= p.end_time)
            total_time += t

        return total_time
