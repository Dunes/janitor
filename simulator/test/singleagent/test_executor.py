__author__ = 'jack'

import unittest
from unittest.mock import MagicMock, Mock, patch, call

from hamcrest import assert_that, contains, is_not, empty, is_, has_length, has_items, equal_to

from singleagent.executor import Executor, CentralPlannerExecutor
from action import ExtraClean, ExtraCleanPart, Move

class TestDeadline(unittest.TestCase):

    @unittest.skip
    def test_set(self):
        executor = Executor(0, agents=("agent",))
        executor.deadline = 10
        assert executor.deadline == 10
        assert executor._deadline == 10

class TestCentralPlannerExecutor(unittest.TestCase):

    def test_replace_extra_clean_actions_with_extra_clean(self):
        # given
        start_time = 0
        duration = 10
        agent0 = "agent0"
        agent1 = "agent1"
        room = "room"
        plan = [ExtraClean(start_time, duration, agent0, agent1, room)]

        # when
        new_plan = list(CentralPlannerExecutor.replace_extra_clean_actions(plan))

        # then
        assert_that(new_plan, has_length(2))
        assert_that(new_plan, has_items(ExtraCleanPart(start_time, duration, agent0, room),
                                  ExtraCleanPart(start_time, duration, agent1, room)))

    def test_disseminate_plan(self):
        # given
        plan = [Move(0, 10, "agent0", "rm0", "rm1"),
                ExtraClean(10, 10, "agent1", "agent0", "rm1"),
                Move(20, 10, "agent1", "rm1", "rm0")]

        # when
        result = CentralPlannerExecutor.disseminate_plan(plan)
        result = [(agent, list(sub_plan)) for agent, sub_plan in result]

        # then
        self.assertEqual("agent0", result[0][0])
        self.assertEqual("agent1", result[1][0])

        self.assertSequenceEqual([plan[0], ExtraCleanPart(10, 10, "agent0", "rm1")],
                                 result[0][1])
        self.assertSequenceEqual([ExtraCleanPart(10, 10, "agent1", "rm1"), plan[2]],
                                 result[1][1])
