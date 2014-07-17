'''
Created on 14 Jul 2014

@author: jack
'''
import unittest

from unittest.mock import Mock

from action_state import ActionState
from planning_exceptions import ExecutionError
from hamcrest import is_, assert_that, is_not, equal_to, less_than, greater_than


class TestActionState(unittest.TestCase):

    def setUp(self):
        self.action_state = ActionState(Mock(name="action_state"))

    def test_can_start(self):
        self.action_state.start()

    def test_can_finish(self):
        self.action_state.start()
        self.action_state.finish()

    def test_cannot_restart(self):
        self.action_state.start()
        with self.assertRaises(ExecutionError):
            self.action_state.start()

    def test_cannot_refinish(self):
        self.action_state.start()
        self.action_state.finish()
        with self.assertRaises(ExecutionError):
            self.action_state.finish()

    def test_cannot_finish_before_start(self):
        with self.assertRaises(ExecutionError):
            self.action_state.finish()


    def test_unpacking(self):
        # given
        action = Mock(name="action")
        time = Mock(name="time")
        state = Mock(name="state")
        action_state = ActionState(action, time, state)

        # when
        actual_time, actual_state, actual_action = action_state

        # then
        assert_that(actual_action, is_(action))
        assert_that(actual_time, is_(time))
        assert_that(actual_state, is_(state))

    def test_is_not_equal(self):

        for attr in ("time", "state", "action"):
            with self.subTest(attr=attr):
                args = {"time": Mock(name="time"), "state": Mock(name="state"), "action": Mock(name="action")}
                first = ActionState(**args)
                args[attr] = Mock(name="not")
                second = ActionState(**args)
                assert_that(first, is_not(second))

    def test_is_equal(self):
        action = Mock(name="action")
        first = ActionState(action)
        second = ActionState(action)

        assert_that(first, equal_to(second))

    def test_is_less_than(self):

        for attr in ("time", "state", "action"):
            with self.subTest(attr=attr):
                args = {"time": 0, "state": 0, "action": 0}
                first = ActionState(**args)
                args[attr] = 1
                second = ActionState(**args)

                assert_that(first, less_than(second))

    def test_is_greater_than(self):

        for attr in ("time", "state", "action"):
            with self.subTest(attr=attr):
                args = {"time": 0, "state": 0, "action": 0}
                first = ActionState(**args)
                args[attr] = -1
                second = ActionState(**args)

                assert_that(first, greater_than(second))

    def test_is_not_less_than(self):

        for attr in ("time", "state", "action"):
            with self.subTest(attr=attr):
                args = {"time": 0, "state": 0, "action": 0}
                first = ActionState(**args)

                assert_that(first, is_not(less_than(first)))

    def test_is_not_greater_than(self):

        for attr in ("time", "state", "action"):
            with self.subTest(attr=attr):
                args = {"time": 0, "state": 0, "action": 0}
                first = ActionState(**args)

                assert_that(first, is_not(greater_than(first)))

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()