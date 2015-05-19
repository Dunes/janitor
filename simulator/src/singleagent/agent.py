__author__ = 'jack'

from logging import getLogger
from logger import StyleAdapter

from decimal import Decimal

import executor
from .requests import ActionRequest
from action import Observe

log = StyleAdapter(getLogger(__name__))


class Agent:

    def __init__(self, name, plan=None, executing=None, plan_valid=False):
        self.name = name
        self.plan = plan
        self.executing = executing
        self.plan_valid = plan_valid
        self.current_plan_execution_limit = None
        self.stalled = None  # whut?

    def next_actions(self, current_time, future_time):
        log.debug("Agent.next_action() current_time={}, future_time={}", current_time, future_time)

        if not self.plan_valid and not self.executing:
            return self.get_plan_request(current_time)
        else:
            actions = self.next_unstalled_actions(future_time)
            self.add_agent_actions_to_executing(actions, future_time)
            return ActionRequest(actions)

    def next_unstalled_actions(self, time: Decimal):
        if time.is_finite() and time > self.current_plan_execution_limit:
            return executor.NoAction.ExecutionLimitReached
        elif self.plan.empty():
            return executor.NoAction.PlanEmpty
        elif self.plan.peek().start_time > time:
            return executor.NoAction.TooEarly

        all_actions = self.plan.get()
        unstalled_actions = [action for action in all_actions if self.is_action_available(action, time)]
        return unstalled_actions

    def is_action_available(self, action, time):
        if time < action.start_time:
            return executor.NoAction.TooEarly
        # elif action.end_time > self.current_plan_execution_limit:
        #     return NoAction.ExecutionLimitReached
        elif action.agents() & self.stalled:
            return executor.NoAction.Stalled
        return True

    def add_agent_actions_to_executing(self, actions, future_time):
        # is this assert what is meant?
        assert sum(1 for action in actions if type(action) is not Observe) <= 1
        for action in actions:
            if type(action) is not Observe:
                assert self.name in action.agents()
                if self.executing and future_time != self.executing.end_time:
                    log.error("'{}' in executing, future_time is {}, current action: {}\nnext action: {}",
                            self.name, future_time, self.executing, action)
                assert not self.executing or future_time == self.executing.end_time
                self.executing = action