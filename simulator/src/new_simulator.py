from enum import Enum
from copy import deepcopy
from accuracy import quantize, round_half_up, increment, as_end_time
from pddl_parser import unknown_value_getter
from action import Action, Plan, Observe, Move, Clean, ExtraClean, Stalled
from action_state import ActionState, ExecutionState
from planning_exceptions import ExecutionError
from logger import StyleAdapter, DummyLogger
from requests import AdjustToPartialRequest

from collections import namedtuple, Iterable
from priority_queue import PriorityQueue
from itertools import chain
from decimal import Decimal
from logging import getLogger

log = StyleAdapter(getLogger(__name__))


class ActionResult(namedtuple("ActionResult", "action time result")):
    def __str__(self):
        return "ActionResult(action={arg.action!s}, time={arg.time!s}, result={arg.result!s})".format(arg=self)

    @staticmethod
    def from_action_state(action_state, model):
        assert action_state.state is ExecutionState.finished
        return ActionResult(action_state.action, round_half_up(action_state.time), action_state.action.apply(model))


class ExecutionProblem(Enum):
    AgentStalled = 0
    ReachedDeadline = 1


class Simulator:

    ID_COUNTER = 0

    def __init__(self, model, executor, planner, plan_logger=None, action_queue=None, time=quantize(0)):
        self.model = model
        self.executor = executor
        self.planner = planner
        self.plan_logger = plan_logger if plan_logger else DummyLogger()
        self.action_queue = action_queue if action_queue else PriorityQueue()
        self.executed = []
        self.stalled = set()
        self.time = time
        self.start_time = self.time
        self.id = self.get_next_id()

    def copy_with(self, *, model=None, executor=None, planner=None, action_queue=None, plan_logger=None, time=None):
        model = model if model else deepcopy(self.model)
        executor = executor if executor else self.executor.copy()
        planner = planner if planner else self.planner
        plan_logger = plan_logger if plan_logger else DummyLogger()
        action_queue = action_queue if action_queue else deepcopy(self.action_queue)
        time = time if time else self.time
        return Simulator(model=model, executor=executor, planner=planner, plan_logger=plan_logger,
            action_queue=action_queue, time=time)

    def run(self, *, deadline=Decimal("Infinity")):
        log.info("Simulator({}).run() deadline={}", self.id, deadline)
        deadline = as_end_time(deadline)
        if self.time > deadline:
            log.info("Simulator({}).run() finished as time ({}) >= deadline ({})", self.id, self.time, deadline)
            return

        if self.action_queue.empty() and not self.process_request(
                self.executor.next_action(self.time, deadline)):
            log.info("Simulator({}).run() finished as no-op", self.id)
            return

        while not self.action_queue.empty() and not self.is_goal_in_model():
            # get next action from queue
            action_state = self.action_queue.get()

            # current action time after deadline, ask executor if it wants to finish any actions early
            if action_state.time > deadline:
                self.action_queue.put(action_state)
                action_request = self.executor.process_result(
                    ActionResult(action_state.action, deadline, ExecutionProblem.ReachedDeadline))
                if self.process_request(action_request):
                    continue
                else:
                    break

            # ask executor if it has an action to start before or at this time
            action_request = self.executor.next_action(self.time, min(action_state.time, deadline))
            if self.process_request(action_request):
                self.action_queue.put(action_state)
                continue

            # if no request then process action
            self.time = action_state.time

            self.process_action_state(action_state)

            # ask executor last chance for next action if queue empty
            if self.action_queue.empty():
                action_request = self.executor.next_action(self.time, deadline)
                self.process_request(action_request)

        log.info("Simulator({}).run() finished", self.id)
        return self.is_goal_in_model()

    def process_action_state(self, action_state):
        log.debug("Simulator({}).process_action_state() action_state={}", self.id, action_state)
        self.time = action_state.time
        if type(action_state.action) is Plan and action_state.state == ExecutionState.pre_start:
            plan, time_taken = self.get_plan(action_state.action.duration)
            action_state = ActionState(action_state.action.copy_with(duration=time_taken, plan=plan))
            action_state.start()
            self.action_queue.put(action_state)
            self.plan_logger.log_plan(plan)
        elif not action_state.action.is_applicable(self.model):
            log.debug("{} has stalled attempting: {}", action_state.action.agents(), action_state.action)
            self.stalled.update((a, action_state.time) for a in action_state.action.agents())
            action_result = ActionResult(action_state.action, action_state.time, ExecutionProblem.AgentStalled)
            request = self.executor.process_result(action_result)
            self.process_request(request)
        elif action_state.state == ExecutionState.pre_start:
            action_state.start()
            self.action_queue.put(action_state)
        elif action_state.state == ExecutionState.executing:
            action_state.finish()
            self.executed.append(action_state.action)
            action_result = ActionResult.from_action_state(action_state, self.model)
            # tell executor about result
            request = self.executor.process_result(action_result)
            self.process_request(request)
        else:
            raise ExecutionError("action_state is invalid {} for time {} with action {}"
                .format(action_state.state, action_state.time, action_state.action))

    def process_request(self, request):
        log.debug("Simulator({}).process_request(), request={}", self.id, request)
        if request is None:
            return False
        elif isinstance(request, Action):
            self.action_queue.put(ActionState(request))
            return True
        elif type(request) is AdjustToPartialRequest:
            adjusted_actions = request.adjust(self.action_queue)
            self.executor.update_executing_actions(adjusted_actions)
            return adjusted_actions
        else:
            raise NotImplementedError("Unknown request type: {}".format(request))

    def get_plan(self, planning_duration):
        log.debug("Simulator({}).get_plan(), planning_duration={}", self.id, planning_duration)
        simulator = self.copy_with(model=self.convert_to_hypothesis_model(self.model))
        simulator.run(deadline=self.time + planning_duration)
        predicted_model = simulator.model
        return self.planner.get_plan_and_time_taken(predicted_model)

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
        stalled_actions = [Stalled(time, min(p.end_time for p in plan_actions if p.end_time > time) - time, agent)
                           for agent, time in self.stalled]
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