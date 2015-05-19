__author__ = 'jack'

import unittest
from unittest.mock import MagicMock, Mock, patch, call

from hamcrest import assert_that, contains, is_not, empty, is_, has_length, has_item, equal_to

from singleagent.simulator import Simulator
from singleagent.executor import Executor
from action import Plan

class TestRun(unittest.TestCase):
    """can't think of any tests -- function quite simple"""

class TestProcessActionStates(unittest.TestCase):
    """can't think of any tests -- function quite simple"""

class TestStartActions(unittest.TestCase):

    def setUp(self):
        self.model = Mock(name="model")

    def test_starts_plan_actions_last(self):
        # given
        agent = "agent"
        executor = Mock(Executor)
        simulator = Simulator(self.model, {"agent": executor}, planner=None)
        plan_action_state = Mock(action=Mock(Plan, **{"agents.return_value": {agent}}),
                                 name="plan_action_state")
        normal_action_state = Mock(action=Mock(**{"agents.return_value": {agent},
                                                  "is_applicable.return_value": True}),
                                   name="normal_action_state")

        # when
        simulator.start_actions((plan_action_state, normal_action_state))

        # then
        executor.notify_action_starting.assert_has_calls([
            call(normal_action_state, self.model),
            call(plan_action_state, self.model)
        ])

    def test_notifies_right_executor_when_single_agent_action_starts(self):
        # given
        right_agent = "right_agent"
        wrong_agent = "wrong_agent"
        right_executor = Mock(Executor)
        wrong_executor = Mock(Executor)
        executors = {right_agent: right_executor, wrong_agent: wrong_executor}
        simulator = Simulator(self.model, executors, planner=None)
        action_state = Mock(["action", "agents"], name="action_state")
        action_state.action.agents.return_value = {right_agent}
        action_state.action.is_applicable.return_value = True

        # when
        simulator.start_actions((action_state,))

        # then
        right_executor.notify_action_starting.assert_called_once_with(action_state, self.model)
        assert_that(wrong_executor.notify_action_starting.call_args_list, is_(empty()))


class TestFinishActions(unittest.TestCase):

    def setUp(self):
        self.model = Mock(name="model")

    def test_notifies_right_executor_when_single_agent_action_finishing(self):
        # given
        right_agent = "right_agent"
        wrong_agent = "wrong_agent"
        right_executor = Mock(Executor)
        wrong_executor = Mock(Executor)
        executors = {right_agent: right_executor, wrong_agent: wrong_executor}
        simulator = Simulator(self.model, executors, planner=None)
        action_state = Mock(["action", "agents"], name="action_state")
        action_state.action.agents.return_value = {right_agent}
        action_state.action.is_applicable.return_value = True

        # when
        simulator.finish_actions((action_state,))

        # then
        right_executor.notify_action_finishing.assert_called_once_with(action_state, self.model)
        assert_that(wrong_executor.notify_action_finishing.call_args_list, is_(empty()))


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()