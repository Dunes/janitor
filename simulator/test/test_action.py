'''
Created on 20 Jun 2014

@author: jack
'''
import unittest
from unittest.mock import Mock, MagicMock
from hamcrest import assert_that, is_not, has_item, anything
import random

import action
from action import ExecutionError
from action_state import ExecutionState

from decimal import Decimal

from util.builder import ModelBuilder
from util.matcher import ModelMatcher, MoveMatcher, CleanMatcher, ExtraCleanMatcher



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

    def test_apply_when_moving_from_temp_node(self):
        self.move.start_node = "temp_start_node"
        distance = 1
        model = ModelBuilder().with_agent("agent", at="temp_start_node") \
            .with_edge("temp_start_node", "end_node").with_edge("end_node", "other_node", distance=distance).model

        self.move.apply(model)

        self.match(model).with_agent("agent").at("end_node")
        self.match(model).with_distance(distance).from_("end_node").to("other_node")
        assert_that(model["nodes"], is_not(has_item("temp_start_node")))
        assert_that(model["graph"]["edges"], is_not(has_item(["temp_start_node", "end_node", distance])))

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


    def test_modify_temp_node_applies_partial_move_forward(self):
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

    def test_modify_temp_node_applies_partial_move_backward(self):
        self.move.start_node = "temp_node"
        self.move.end_node = "start_node"
        deadline = Decimal("1.6")
        to_start = Decimal(12)
        to_end = Decimal(15)
        model = ModelBuilder().with_agent("agent", at="temp_node") \
            .with_edge("temp_node", "start_node", to_start) \
            .with_edge("temp_node", "end_node", to_end).model

        self.move.modify_temp_node(model, deadline)

        movement = deadline - self.move.start_time
        self.match(model).with_agent("agent").at("temp_node")
        self.match(model).with_distance(to_start - movement).from_("temp_node").to("start_node")
        self.match(model).with_distance(to_end + movement).from_("temp_node").to("end_node")


    def test_partially_apply_selects_create(self):
        expected = object()
        deadline = object()
        self.move.is_applicable = Mock(return_value=True)
        self.move.create_temp_node = Mock(return_value=expected)
        model = ModelBuilder().with_node("node").model

        actual = self.move.partially_apply(model, deadline)

        self.move.is_applicable.assert_called_once_with(model)
        self.move.create_temp_node.assert_called_once_with(model, deadline)
        self.assertEqual(expected, actual)


    def test_partially_apply_selects_modify(self):
        expected = Mock()
        deadline = Mock()
        model = Mock()
        self.move.start_node = "temp_node"
        self.move.is_applicable = Mock(return_value=True)
        self.move.modify_temp_node = Mock(return_value=expected)
        self.move.create_temp_node = Mock()

        actual = self.move.partially_apply(model, deadline)

        self.move.is_applicable.assert_called_once_with(model)
        self.move.modify_temp_node.assert_called_once_with(model, deadline)
        self.assertEqual(expected, actual)



class ObserveTest(unittest.TestCase):

    def setUp(self):
        self.match = ModelMatcher(self)
        self.observe = action.Observe(Decimal(1), "agent", "node")
        action.debug = True

    def tearDown(self):
        action.debug = False

    def test_is_applicable(self):
        model = ModelBuilder().with_agent("agent", at="node").model
        expected = True
        actual = self.observe.is_applicable(model)
        self.assertEqual(expected, actual)

    def test_is_not_applicable(self):
        model = ModelBuilder().with_agent("agent", at="elsewhere").model
        expected = False
        actual = self.observe.is_applicable(model)
        self.assertEqual(expected, actual)

    def test_check_new_knowledge_is_true(self):
        unknown_values = {"key": {"actual": 0}}
        assumed_values = {"key": 1}

        actual = self.observe._check_new_knowledge(unknown_values, assumed_values)

        self.assertEqual(True, actual)

    def test_check_new_knowledge_is_false(self):
        unknown_values = {"key": {"actual": 0}}
        assumed_values = {"key": 0}

        actual = self.observe._check_new_knowledge(unknown_values, assumed_values)

        self.assertEqual(False, actual)

    def test_apply_with_new_knowledge(self):
        unknown = {"k": "v"}
        known = {}
        self.observe._get_actual_value = Mock(side_effect=lambda x: x)
        model = ModelBuilder().with_assumed_values().with_node("node", unknown=unknown, known=known).model
        self.observe.is_applicable = Mock(return_value=True)
        self.observe._check_new_knowledge = Mock(return_value=True)

        actual = self.observe.apply(model)

        self.match(model).with_node("node", known={"k": "v"}, unknown={})
        self.assertEqual(True, actual)


    def test_apply_with_no_new_knowledge(self):
        unknown = {}
        known = {"k": "v"}
        self.observe._get_actual_value = Mock(side_effect=lambda x: x)
        model = ModelBuilder().with_node("node", unknown=unknown, known=known).model
        self.observe.is_applicable = Mock(return_value=True)
        self.observe._check_new_knowledge = Mock(return_value=False)

        actual = self.observe.apply(model)

        self.match(model).with_node("node", known={"k": "v"}, unknown={})
        self.assertEqual(False, actual)

    def test_apply_with_no_unknown(self):
        model = ModelBuilder().with_node("node").model
        self.observe.is_applicable = Mock(return_value=True)

        actual = self.observe.apply(model)

        self.assertEqual(False, actual)


class CleanTest(unittest.TestCase):

    def setUp(self):
        self.match = ModelMatcher(self)
        self.clean = action.Clean(Decimal(0), Decimal(1), "agent", "room")
        action.debug = True

    def tearDown(self):
        action.debug = False

    def test_is_applicable(self):
        model = ModelBuilder().with_agent("agent", at="room") \
            .with_node("room", known={"extra-dirty": False}).model

        actual = self.clean.is_applicable(model)

        self.assertEqual(True, actual)

    def test_is_not_applicable_because_agent_elsewhere(self):
        model = ModelBuilder().with_agent("agent", at="elsewhere") \
            .with_node("room", known={"extra-dirty": False}).model

        actual = self.clean.is_applicable(model)

        self.assertEqual(False, actual)

    def test_is_not_applicable_because_extra_dirty(self):
        model = ModelBuilder().with_agent("agent", at="room") \
            .with_node("room", known={"extra-dirty": True}).model

        actual = self.clean.is_applicable(model)

        self.assertEqual(False, actual)

    def test_is_not_applicable_because_extra_dirty_is_assumed_if_not_known(self):
        model = ModelBuilder().with_agent("agent", at="room").with_node("room").model

        actual = self.clean.is_applicable(model)

        self.assertEqual(False, actual)

    def test_apply(self):
        node_value = MagicMock()
        model = ModelBuilder().with_node("room", value=node_value).model
        self.clean.is_applicable = Mock(return_value=True)

        actual = self.clean.apply(model)

        node_value.__getitem__.assert_called_once_with("known")
        known_values = node_value["known"]
        known_values.__delitem__.assert_called_once("dirty")
        known_values.__delitem__.assert_called_once("dirtiness")
        known_values.__setitem__.assert_called_once_with("cleaned", True)
        self.assertEqual(False, actual)

    def test_partially_apply(self):
        node = MagicMock(name="node")
        node.__getitem__().__getitem__().__le__.return_value = False # prevents logging branch
        deadline = Decimal("0.6")
        duration = deadline - self.clean.start_time
        model = ModelBuilder().with_node("room", value=node).model
        self.clean.is_applicable = Mock(return_value=True)

        expected = action.Clean(self.clean.start_time, duration, "agent", "room", True)

        actual = self.clean.partially_apply(model, deadline)

        node.__getitem__.assert_called_with("known")
        node["known"].__setitem__.assert_called_once("dirtiness", duration)
        CleanMatcher(self).assertEqual(expected, actual)


class ExtraCleanTest(unittest.TestCase):

    def setUp(self):
        self.match = ModelMatcher(self)
        self.extra_clean = action.ExtraClean(Decimal(0), Decimal(1), "agent0", "agent1", "room")
        action.debug = True

    def tearDown(self):
        action.debug = False

    def test_is_applicable(self):
        model = ModelBuilder().with_agent("agent0", at="room") \
            .with_agent("agent1", at="room") \
            .with_node("room", known={"dirty": False}).model

        actual = self.extra_clean.is_applicable(model)

        self.assertEqual(True, actual)

    def test_is_not_applicable_because_agent_elsewhere(self):
        model = ModelBuilder().with_agent("agent0", at="elsewhere") \
            .with_agent("agent1", at="elsewhere") \
            .with_node("room", known={"dirty": False}).model

        actual = self.extra_clean.is_applicable(model)

        self.assertEqual(False, actual)

    def test_is_not_applicable_because_extra_dirty(self):
        model = ModelBuilder().with_agent("agent0", at="room") \
            .with_agent("agent1", at="room") \
            .with_node("room", known={"dirty": True}).model

        actual = self.extra_clean.is_applicable(model)

        self.assertEqual(False, actual)

    def test_is_not_applicable_because_extra_dirty_is_assumed_if_not_known(self):
        model = ModelBuilder().with_agent("agent0", at="room") \
            .with_agent("agent1", at="room") \
            .with_node("room").model

        actual = self.extra_clean.is_applicable(model)

        self.assertEqual(False, actual)

    def test_apply(self):
        node_value = MagicMock()
        model = ModelBuilder().with_node("room", value=node_value).model
        self.extra_clean.is_applicable = Mock(return_value=True)

        actual = self.extra_clean.apply(model)

        node_value.__getitem__.assert_called_once_with("known")
        known_values = node_value["known"]
        known_values.__delitem__.assert_called_once("extra-dirty")
        known_values.__delitem__.assert_called_once("dirtiness")
        known_values.__setitem__.assert_called_once_with("cleaned", True)
        self.assertEqual(False, actual)

    def test_partially_apply(self):
        node_value = MagicMock()
        deadline = Decimal("0.6")
        duration = deadline - self.extra_clean.start_time
        model = ModelBuilder().with_node("room", value=node_value).model
        self.extra_clean.is_applicable = Mock(return_value=True)

        expected = action.ExtraClean(self.extra_clean.start_time, duration, "agent0", "agent1", "room", True)

        actual = self.extra_clean.partially_apply(model, deadline)

        node_value.__getitem__.assert_called_once_with("known")
        node_value["known"].__setitem__.assert_called_once("dirtiness", duration)
        ExtraCleanMatcher(self).assertEqual(expected, actual)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()