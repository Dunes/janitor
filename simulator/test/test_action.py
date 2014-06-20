'''
Created on 20 Jun 2014

@author: jack
'''
import unittest
import random

import action
from action import ExecutionState, ExecutionError

from decimal import Decimal

from util.model import ModelBuilder
from util.matcher import ModelMatcher, MoveMatcher
from unittest.case import skip

class ExecutionStateTest(unittest.TestCase):

    def test_ordering(self):
        sequence = list(ExecutionState)
        random.shuffle(sequence)
        expected_order = [ExecutionState.finished, ExecutionState.executing,
                 ExecutionState.pre_start]
        self.assertListEqual(expected_order, sorted(sequence))

class ActionOrderingTest(unittest.TestCase):

    def test_ordering(self):
        """Test ordering is correct and _stable_"""
        action_ = action.Action(0, 0)
        plan = action.Plan(0, 0)
        observe = action.Observe(0, "agent", "node")
        move = action.Move(0, 0, "agent", "start_node", "end_node")
        clean = action.Clean(0, 0, "agent", "room")
        extra_clean = action.ExtraClean(0, 0, "agent0", "agent1", "room")

        actual = sorted([action_, plan, observe, move, clean, extra_clean])
        expected = [move, observe, action_, plan, clean, extra_clean]
        self.assertListEqual(expected, actual)

    def test_move_before_observe(self):
        observe = action.Observe(0, "agent", "node")
        move = action.Move(0, 0, "agent", "start_node", "end_node")
        self.assertLess(move, observe)

    def test_observe_before_others(self):
        observe = action.Observe(0, "agent", "node")

        action_ = action.Action(0, 0)
        plan = action.Plan(0, 0)
        clean = action.Clean(0, 0, "agent", "room")
        extra_clean = action.ExtraClean(0, 0, "agent0", "agent1", "room")

        others = [action_, plan, clean, extra_clean]

        for other in others:
            self.assertLess(observe, other)


class ActionTest(unittest.TestCase):

    def setUp(self):
        self.action = action.Action(Decimal("0.100"), Decimal("1.050"))

    def test_can_start(self):
        self.action.start()

    def test_can_finish(self):
        self.action.start()
        self.action.finish()

    def test_cannot_restart(self):
        self.action.start()
        self.assertRaises(ExecutionError, self.action.start)

    def test_cannot_refinish(self):
        self.action.start()
        self.action.finish()
        self.assertRaises(ExecutionError, self.action.finish)

    def test_cannot_finish_before_start(self):
        self.assertRaises(ExecutionError, self.action.finish)

    def test_calculates_endtime(self):
        expected_endtime = self.action.start_time + self.action.duration
        self.assertEquals(expected_endtime, self.action.end_time)

class MoveTest(unittest.TestCase):

    def setUp(self):
        self.match = ModelMatcher(self)
        self.move = action.Move(Decimal(1), Decimal(2), "agent", "start_node", "end_node")
        action.debug = True

    def tearDown(self):
        action.debug = False

    def test_is_applicable(self):
        model = ModelBuilder().with_agent("agent", at="start_node").model
        expected = True
        actual = self.move.is_applicable(model)
        self.assertEqual(expected, actual)

    def test_is_not_applicable(self):
        model = ModelBuilder().with_agent("agent", at="elsewhere").model
        expected = False
        actual = self.move.is_applicable(model)
        self.assertEqual(expected, actual)

    def test_apply(self):
        model = ModelBuilder().with_agent("agent", at="start_node").model
        self.move.apply(model)
        self.match(model).with_agent("agent").at("end_node")

    def test_apply_fail_when_debug(self):
        model = ModelBuilder().with_agent("agent", at="elsewhere").model
        self.assertRaises(ExecutionError, self.move.apply, model)

    def test_create_temp_node_creates_partial_action(self):
        deadline = Decimal("1.6")
        model = ModelBuilder().with_agent("agent", at="start_node").model
        expected_action = action.Move(self.move.start_time, Decimal("0.6"), "agent",
                "start_node", "temp-agent-start_node-end_node", True)

        actual_action = self.move.create_temp_node(model, deadline)

        MoveMatcher(self).assertEqual(expected_action, actual_action)


    def test_create_temp_node_applies_partial_move(self):
        deadline = Decimal("1.6")
        model = ModelBuilder().with_agent("agent", at="start_node").model
        temp_node = "temp-agent-start_node-end_node"

        self.move.create_temp_node(model, deadline)

        self.match(model).with_agent("agent").at(temp_node)
        self.match(model).with_distance(deadline - self.move.start_time).from_(temp_node).to(self.move.start_node)
        self.match(model).with_distance(self.move.end_time - deadline).from_(temp_node).to(self.move.end_node)


    def test_modify_temp_node_creates_partial_move(self):
        self.move.start_node = "temp_node"
        deadline = Decimal("1.6")
        model = ModelBuilder().with_agent("agent", at="temp_node") \
            .with_edge("temp_node", "start_node", Decimal(12)) \
            .with_edge("temp_node", "end_node", Decimal(15)).model

        expected_action = action.Move(self.move.start_time, Decimal("0.6"), "agent",
                "temp_node", "end_node", True)

        actual_action = self.move.modify_temp_node(model, deadline)

        MoveMatcher(self).assertEqual(expected_action, actual_action)


    def test_modify_temp_node_applies_partial_move(self):
        self.move.start_node = "temp_node"
        deadline = Decimal("1.6")
        to_start = Decimal(12)
        to_end = Decimal(15)
        model = ModelBuilder().with_agent("agent", at="temp_node") \
            .with_edge("temp_node", "start_node", to_start) \
            .with_edge("temp_node", "end_node", to_end).model

        self.move.modify_temp_node(model, deadline)

        movement = deadline - self.move.start_time
        self.match(model).with_agent("agent").at("temp_node")
        self.match(model).with_distance(to_start + movement).from_("temp_node").to("start_node")
        self.match(model).with_distance(to_end - movement).from_("temp_node").to("end_node")


    @skip("requires mocking to test")
    def test_partially_apply(self):
        pass

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()