__author__ = 'jack'

from collections import Iterable
from logging import getLogger
from operator import attrgetter
from decimal import Decimal
from accuracy import quantize, as_end_time, as_start_time
from singleagent.agent import Agent
from action import Plan, Observe, Move, GetExecutionHeuristic
from action_state import ExecutionState
from copy import copy
from logger import StyleAdapter
from new_simulator import ExecutionProblem
from priority_queue import MultiActionQueue
from requests import AdjustToPartialRequest, RemoveActionsWithStateRequest, ActionRequest, MultiRequest
from planning_exceptions import ExecutionError
from itertools import count

log = StyleAdapter(getLogger(__name__))


class Executor:

    ID_COUNTER = count()

    def notify_action_starting(self, action_state, model):
        raise NotImplementedError

    def notify_action_finishing(self, action_state, model):
        raise NotImplementedError

    @property
    def deadline(self):
        return self._deadline

    @deadline.setter
    def deadline(self, deadline):
        self._deadline = deadline

    def __init__(self, planning_duration, *, plan=None, executing=None, stalled=None,
            current_plan_execution_limit=Decimal("Infinity"), last_observation=quantize(-1), plan_valid=False,
            agents):
        self.started = False
        self.plan = plan or MultiActionQueue()
        self.executing = executing or {}
        self.stalled = stalled or set()
        self.planning_duration = planning_duration
        self.current_plan_execution_limit = current_plan_execution_limit
        self.last_observation = last_observation
        self.plan_valid = plan_valid
        self.agents = agents
        self.id = next(self.ID_COUNTER)

    def copy(self):
        log.debug("Executor.copy()")
        return Executor(self.planning_duration, plan=copy(self.plan),
            executing=dict(self.executing), current_plan_execution_limit=self.current_plan_execution_limit,
            last_observation=self.last_observation, plan_valid=self.plan_valid, agents=self.agents)

    def next_actions(self, current_time, future_time):
        log.debug("Executor.next_action() current_time={}, future_time={}", current_time, future_time)
        requests = []
        for agent in self.agents.values():
            req = self.next_action(agent, current_time)
            if req:
                requests.append(req)
        return MultiRequest(requests)

    def process_results(self, results):
        log.debug("Executor.process_results() results={}", results)
        requests = []
        for result in results:
            request = self.process_result(result)
            if request:
                requests.append(request)
        return MultiRequest(requests) if requests else None

    def process_result(self, result):
        if type(result.action) not in (Observe, list):
            for agent in result.action.agents():
                if self.match_action(self.executing[agent], result.action):
                    del self.executing[agent]

        if type(result.action) is Plan:
            self.truncate_plan(as_start_time(self.current_plan_execution_limit))

            expected_plan_end = result.action.start_time + self.get_plan_start_time_adjustment(result.action.duration)
            self.plan.put(self.adjust_plan(result.result, expected_plan_end))
            self.current_plan_execution_limit = Decimal("Infinity")
            self.stalled.clear()
            return self.get_request_for_plan_complete(expected_plan_end)
        elif type(result.action) is GetExecutionHeuristic:
            applicable_actions = self.plan.get_ends_before(as_start_time(self.current_plan_execution_limit))
            self.plan = MultiActionQueue(applicable_actions + self.adjust_plan(result.result, result.time))
            self.truncate_plan(as_start_time(self.current_plan_execution_limit))
            self.stalled.clear()
            return self.next_actions(result.time, self.current_plan_execution_limit)
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

    @staticmethod
    def match_action(action0, action1):
        if action0 == action1 or (type(action0) is Plan and type(action1) is Plan):
            return True
        elif type(action0) == type(action1) and action0.start_time == action1.start_time \
                and action0.agents() == action1.agents():
            log.warning("Matching two actions with different end times {} and {}".format(action0, action1))
            return True
        return False

    def get_plan_request(self, agent: Agent, time: Decimal) -> ActionRequest:
        if agent.plan_valid or agent.executing:
            return None
        plan = self.get_plan_action(time)  # incorporate agent name
        agent.current_plan_execution_limit = self.get_state_prediction_end_time(plan)
        agent.executing = plan
        agent.plan_valid = True
        self.last_observation = plan.start_time  # TODO: is this needed still?
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

    def truncate_plan(self, deadline):
        sub_plan = [
            action if action.end_time < deadline else
            action.as_partial(duration=as_start_time(deadline - action.start_time))
            for action in self.plan.get_starts_before(deadline)
        ]
        self.plan = MultiActionQueue(sub_plan)

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

    def get_plan_start_time_adjustment(self, actual_planning_duration):
        # should be "actual_planning_duration" mostly, except if planner is using state prediction
        # in which case it should be self.planning_duration
        raise NotImplementedError()

    def get_additional_plan_requests(self, time):
        raise NotImplementedError()