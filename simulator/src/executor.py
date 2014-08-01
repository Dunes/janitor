from collections import Iterable
from logging import getLogger
from enum import Enum
from operator import attrgetter
from decimal import Decimal
from accuracy import quantize, as_end_time, as_start_time
from action import Plan, Observe, Move
from action_state import ExecutionState
from copy import copy
from logger import StyleAdapter
from new_simulator import ExecutionProblem
from priority_queue import MultiActionQueue
from requests import AdjustToPartialRequest, RemoveActionsWithStateRequest, ActionRequest, MultiRequest
from planning_exceptions import ExecutionError

log = StyleAdapter(getLogger(__name__))


class NoAction(Enum):
    PlanEmpty = 1
    TooEarly = 2
    ExecutionLimitReached = 3
    Stalled = 4

    def __bool__(self):
        return False


class Executor:

    ID_COUNTER = 0

    def __init__(self, planning_duration, *, plan=None, executing=None, stalled=None,
            current_plan_execution_limit=Decimal("Infinity"), last_observation=quantize(-1), plan_valid=False):
        self.started = False
        self.plan = plan if plan else MultiActionQueue()
        self.executing = executing if executing else {}
        self.stalled = stalled if stalled else set()
        self.planning_duration = planning_duration
        self.current_plan_execution_limit = current_plan_execution_limit
        self.last_observation = last_observation
        self.plan_valid = plan_valid
        self.id = Executor.get_next_id()

    def copy(self):
        log.debug("Executor.copy()")
        return type(self)(self.planning_duration, plan=copy(self.plan), executing=dict(self.executing),
            current_plan_execution_limit=self.current_plan_execution_limit, last_observation=self.last_observation,
            plan_valid=self.plan_valid)

    def next_actions(self, current_time, future_time):
        log.debug("Executor.next_action() current_time={}, future_time={}", current_time, future_time)
        if not self.plan_valid and Plan.agent not in self.executing:
            return self.get_plan_request(current_time)
        actions = self.next_unstalled_actions(future_time)
        if not actions or isinstance(actions, NoAction):
            return None

        self.add_agent_actions_to_executing(actions, future_time)

        return ActionRequest(actions)

    def add_agent_actions_to_executing(self, actions, future_time):
        for action in actions:
            if type(action) is not Observe:
                for agent in action.agents():
                    if agent in self.executing and future_time != self.executing[agent].end_time:
                        log.error("'{}' in executing, future_time is {}, current action: {}\nnext action: {}",
                            agent, future_time, self.executing[agent], action)
                    assert agent not in self.executing or future_time == self.executing[agent].end_time
                    self.executing[agent] = action

    def is_action_available(self, action, time):
        if time < action.start_time:
            return NoAction.TooEarly
        elif action.end_time > self.current_plan_execution_limit:
            return NoAction.ExecutionLimitReached
        elif action.agents() & self.stalled:
            return NoAction.Stalled
        return True

    def next_unstalled_actions(self, time: Decimal):
        if time.is_finite() and time >= self.current_plan_execution_limit:
            return NoAction.ExecutionLimitReached
        elif self.plan.empty():
            return NoAction.PlanEmpty
        elif self.plan.peek().start_time > time:
            return NoAction.TooEarly

        all_actions = self.plan.get()
        unstalled_actions = [action for action in all_actions if self.is_action_available(action, time)]
        return unstalled_actions

    def process_results(self, results):
        log.debug("Executor.process_results() results={}", results)
        requests = []
        for result in results:
            request = self.process_result(result)
            if request:
                requests.append(request)
        return MultiRequest(requests) if requests else None

    def process_result(self, result):
        if type(result.action) is not Observe:
            for agent in result.action.agents():
                if self.executing[agent] == result.action or type(result.action) is Plan:
                    del self.executing[agent]

        if type(result.action) is Plan:
            self.current_plan_execution_limit = Decimal("Infinity")
            request = self.get_request_for_plan_complete(result.time)
            self.plan = MultiActionQueue(self.adjust_plan(result.result, result.time))
            self.stalled.clear()
            return request
        elif result.result == ExecutionProblem.ReachedDeadline:
            return self.get_request_for_reached_deadline(result.time)
        elif result.result == ExecutionProblem.AgentStalled:
            self.stalled |= result.action.agents()
            return None
        elif result.result is True:
            if self.last_observation < result.time:
                self.plan_valid = False
                self.last_observation = result.time
            return self.get_plan_request(result.time)
        elif result.result is False:
            return None
        else:
            raise ExecutionError("Unknown value for result {}".format(result))

    def get_plan_request(self, time: Decimal) -> Plan:
        if self.plan_valid or Plan.agent in self.executing:
            return None
        plan = self.get_plan_action(time)
        self.current_plan_execution_limit = self.get_state_prediction_end_time(plan)
        self.executing[Plan.agent] = plan
        self.plan_valid = True
        self.last_observation = plan.start_time
        other_requests = self.get_additional_plan_requests(plan.start_time)
        if other_requests:
            return ActionRequest((plan,)) + other_requests
        else:
            return ActionRequest((plan,))

    def update_executing_actions(self, adjusted_actions):
        if not isinstance(adjusted_actions, Iterable):
            return
        for change in adjusted_actions:
            if change.action:
                for agent in change.agents:
                    self.executing[agent] = change.action
            else:
                for agent in change.agents:
                    self.executing.pop(agent, None)

    def adjust_plan(self, plan, start_time):
        return sorted(self._adjust_plan_helper(plan, start_time), key=attrgetter("start_time", "_ordinal"))

    @staticmethod
    def _adjust_plan_helper(plan, start_time):
        for action in plan:
            # adjust for OPTIC starting at t = 0
            action = action.copy_with(start_time=action.start_time + start_time)
            yield action
            if type(action) is Move:
                yield Observe(action.end_time, action.agent, action.end_node)

    def get_plan_action(self, time: Decimal) -> Plan:
        raise NotImplementedError()

    def get_request_for_plan_complete(self, time):
        raise NotImplementedError()

    def get_request_for_reached_deadline(self, time):
        raise NotImplementedError()

    def get_state_prediction_end_time(self, plan):
        raise NotImplementedError()

    def get_additional_plan_requests(self, time):
        return None

    @classmethod
    def get_next_id(cls):
        id_ = cls.ID_COUNTER
        cls.ID_COUNTER += 1
        return id_


class PartialExecutionOnObservationAndStatePredictionExecutor(Executor):

    def get_plan_action(self, time: Decimal) -> Plan:
        return Plan(as_start_time(time), self.planning_duration)

    def get_request_for_plan_complete(self, time):
        return AdjustToPartialRequest(time)

    def get_request_for_reached_deadline(self, time):
        return AdjustToPartialRequest(time)

    def get_state_prediction_end_time(self, plan):
        return plan.end_time


class PartialExecutionOnObservationExecutor(Executor):

    def get_plan_action(self, time: Decimal) -> Plan:
        return Plan(as_start_time(time), self.planning_duration)

    def get_request_for_plan_complete(self, time):
        return None

    def get_request_for_reached_deadline(self, time):
        return AdjustToPartialRequest(time)

    def get_state_prediction_end_time(self, plan):
        return as_end_time(plan.start_time)

    def get_additional_plan_requests(self, time):
        return AdjustToPartialRequest(as_end_time(time))


class FinishActionsAndUseStatePredictionExecutor(Executor):

    def get_plan_action(self, time: Decimal) -> Plan:
        if self.executing:
            max_end_of_executing_action = max(a.end_time for a in self.executing.values() if a.start_time < time)
            return Plan(as_start_time(max_end_of_executing_action) - self.planning_duration, self.planning_duration)
        else:
            return Plan(as_start_time(time), self.planning_duration)

    def get_request_for_plan_complete(self, time):
        return RemoveActionsWithStateRequest(time, ExecutionState.pre_start, ExecutionState.executing)

    def get_request_for_reached_deadline(self, time):
        # TODO: could return None
        return RemoveActionsWithStateRequest(time, ExecutionState.pre_start, ExecutionState.executing)

    def get_state_prediction_end_time(self, plan):
        return plan.end_time


class FinishActionsExecutor(Executor):

    def get_plan_action(self, time: Decimal) -> Plan:
        if self.executing:
            max_end_of_executing_action = max(a.end_time for a in self.executing.values() if a.start_time < time)
            return Plan(as_start_time(max_end_of_executing_action), self.planning_duration)
        else:
            return Plan(as_start_time(time), self.planning_duration)

    def get_request_for_plan_complete(self, time):
        return RemoveActionsWithStateRequest(time, ExecutionState.pre_start, ExecutionState.executing)

    def get_request_for_reached_deadline(self, time):
        # TODO: could return None
        return RemoveActionsWithStateRequest(time, ExecutionState.pre_start, ExecutionState.executing)

    def get_state_prediction_end_time(self, plan):
        return as_end_time(plan.start_time)