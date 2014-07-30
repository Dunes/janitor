from logging import getLogger
from enum import Enum
from operator import attrgetter
from decimal import Decimal
from accuracy import quantize, round_half_up, as_end_time
from action import Plan, Observe, Move
from action_state import ExecutionState
from logger import StyleAdapter
from new_simulator import ExecutionProblem
from requests import AdjustToPartialRequest, RemoveActionsWithStateRequest
from planning_exceptions import ExecutionError

log = StyleAdapter(getLogger(__name__))


class NoAction(Enum):
    PlanEmpty = 1
    TooEarly = 2


class Executor:

    ID_COUNTER = 0

    def __init__(self, planning_duration, *, plan=None, executing=None, stalled=None, last_observation=quantize(-1),
            plan_valid=False):
        self.started = False
        self.plan = plan if plan else []
        self.executing = executing if executing else {}
        self.stalled = stalled if stalled else set()
        self.planning_duration = planning_duration
        self.last_observation = last_observation
        self.plan_valid = plan_valid
        self.id = Executor.get_next_id()

    def copy(self):
        log.debug("Executor.copy()")
        return type(self)(self.planning_duration, plan=list(self.plan), executing=dict(self.executing),
            last_observation=self.last_observation, plan_valid=self.plan_valid)

    def next_action(self, current_time, future_time):
        log.debug("Executor.next_action() current_time={}, future_time={}", current_time, future_time)
        if not self.plan_valid and Plan.agent not in self.executing:
            return self.get_plan_request(current_time)
        action = self.next_unstalled_action(future_time)
        if action is NoAction.PlanEmpty:
            plan_action = self.get_plan_request(current_time)
            assert plan_action is None
            return plan_action
        elif action is NoAction.TooEarly:
            return None
        elif type(action) is not Observe:
            for agent in action.agents():
                if agent in self.executing and future_time != self.executing[agent].end_time:
                    log.error("'{}' in executing, future_time is {}, current action: {}\nnext action: {}",
                        agent, future_time, self.executing[agent], action)
                assert agent not in self.executing or future_time == self.executing[agent].end_time
                self.executing[agent] = action
        return action

    def next_unstalled_action(self, time):
        while self.plan:
            action = self.plan[-1]
            if time < action.start_time:
                log.info("no action starting before {}", time)
                return NoAction.TooEarly
            if action.agents() & self.stalled:
                log.debug("Discarding stalled agent action: {}", action)
                self.plan.pop()
            else:
                return self.plan.pop()
        log.info("No valid action available")
        return NoAction.PlanEmpty

    def process_result(self, result):
        log.debug("Executor.process_result() result={}", result)

        if type(result.action) is not Observe:
            for agent in result.action.agents():
                if self.executing[agent] == result.action or type(result.action) is Plan:
                    del self.executing[agent]

        if type(result.action) is Plan:
            request = self.get_request_for_plan_complete(result.time)
            self.plan = self.adjust_plan(result.result, result.time)
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
        self.executing[Plan.agent] = plan
        self.plan_valid = True
        self.last_observation = plan.start_time
        return plan

    def update_executing_actions(self, adjusted_actions):
        for change in adjusted_actions:
            if change.action:
                for agent in change.agents:
                    self.executing[agent] = change.action
            else:
                for agent in change.agents:
                    self.executing.pop(agent, None)

    def adjust_plan(self, plan, start_time):
        return sorted(self._adjust_plan_helper(plan, start_time),
            key=attrgetter("start_time"), reverse=True)

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

    def get_state_prediction_end_time(self):
        raise NotImplementedError()

    @classmethod
    def get_next_id(cls):
        id_ = cls.ID_COUNTER
        cls.ID_COUNTER += 1
        return id_


class PredictStateAtPlannerFinishExecutor(Executor):

    def get_plan_action(self, time: Decimal) -> Plan:
        return Plan(round_half_up(time), self.planning_duration)

    def get_request_for_plan_complete(self, time):
        return AdjustToPartialRequest(time)

    def get_request_for_reached_deadline(self, time):
        return AdjustToPartialRequest(time)

    def get_state_prediction_end_time(self):
        return self.executing[Plan.agent].end_time


class FinishActionsOnObservationExecutor(Executor):

    def get_plan_action(self, time: Decimal) -> Plan:
        if self.executing:
            max_end_of_executing_action = max(a.end_time for a in self.executing.values() if a.start_time < time)
            return Plan(round_half_up(max_end_of_executing_action) - self.planning_duration, self.planning_duration)
        else:
            return Plan(round_half_up(time), self.planning_duration)

    def get_request_for_plan_complete(self, time):
        return RemoveActionsWithStateRequest(time, ExecutionState.pre_start, ExecutionState.executing)

    def get_request_for_reached_deadline(self, time):
        return RemoveActionsWithStateRequest(time, ExecutionState.pre_start, ExecutionState.executing)

    def get_state_prediction_end_time(self):
        return self.executing[Plan.agent].end_time