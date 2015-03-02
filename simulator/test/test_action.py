"""
Created on 2ZERO Jun 2ZERO14

@author: jack
"""
import unittest
from unittest.mock import Mock, MagicMock, ANY, patch
from hamcrest import assert_that, is_not, has_item, equal_to, less_than, greater_than
import random

import action
from action_state import ExecutionState
from accuracy import as_start_time, as_end_time


from decimal import Decimal

from util.builder import ModelBuilder
from util.matchers import has_agent, has_edge, has_node


ZERO = Decimal("0")


class ExecutionStateTest(unittest.TestCase):

    def test_ordering(self):
        sequence = list(ExecutionState)
        random.shuffle(sequence)
        expected_order = [ExecutionState.finished, ExecutionState.executing,
                 ExecutionState.pre_start]
        assert_that(sorted(sequence), equal_to(expected_order))


class ActionOrderingTest(unittest.TestCase):

    def test_ordering(self):
        """Test ordering is correct and _stable_"""
        action_ = action.Action(ZERO, ZERO)
        plan = action.Plan(ZERO, ZERO)
        observe = action.Observe(ZERO, "agent", "node")
        move = action.Move(ZERO, ZERO, "agent", "start_node", "end_node")
        clean = action.Clean(ZERO, ZERO, "agent", "room")
        extra_clean = action.ExtraClean(ZERO, ZERO, "agent0", "agent1", "room")

        actual = sorted([action_, plan, observe, move, clean, extra_clean])
        expected = [action_, move, clean, extra_clean, observe, plan]
        assert_that(actual, equal_to(expected))

    def test_observe_after_other_actions(self):
        observe = action.Observe(ZERO, "agent", "node")

        action_ = action.Action(ZERO, ZERO)
        move = action.Move(ZERO, ZERO, "agent", "start_node", "end_node")
        clean = action.Clean(ZERO, ZERO, "agent", "room")
        extra_clean = action.ExtraClean(ZERO, ZERO, "agent0", "agent1", "room")

        others = [action_, move, clean, extra_clean]

        for other in others:
            with self.subTest(other=other):
                assert_that(observe, greater_than(other))


class ActionTest(unittest.TestCase):

    def setUp(self):
        self.action = action.Action(Decimal("0"), Decimal("2"))

    def test_calculates_endtime(self):
        expected_endtime = as_end_time(self.action.start_time + self.action.duration)
        assert_that(self.action.end_time, equal_to(expected_endtime))


class MoveTest(unittest.TestCase):

    def setUp(self):
        self.move = action.Move(Decimal(1), Decimal(2), "agent", "start_node", "end_node")

    def test_is_applicable(self):
        model = ModelBuilder().with_agent("agent", at="start_node").model
        actual = self.move.is_applicable(model)
        assert_that(actual)

    def test_is_not_applicable(self):
        model = ModelBuilder().with_agent("agent", at="elsewhere").model
        actual = self.move.is_applicable(model)
        assert_that(is_not(actual))

    def test_apply(self):
        model = ModelBuilder().with_agent("agent", at="start_node").model
        self.move.apply(model)
        assert_that(model, has_agent("agent").at("end_node"))

    def test_apply_fail(self):
        model = ModelBuilder().with_agent("agent", at="elsewhere").model
        with self.assertRaises(AssertionError):
            self.move.apply(model)

    def test_apply_when_moving_from_temp_node(self):
        object.__setattr__(self.move, "start_node", "temp_start_node")
        distance = 1
        model = ModelBuilder().with_agent("agent", at="temp_start_node") \
            .with_edge("temp_start_node", "end_node").with_edge("end_node", "other_node", distance=distance).model

        self.move.apply(model)

        assert_that(model, has_agent("agent").at("end_node"))
        assert_that(model, has_agent("agent").at("end_node"))
        assert_that(model["nodes"], is_not(has_item("temp_start_node")))
        assert_that(model["graph"]["edges"], is_not(has_item(["temp_start_node", "end_node", distance])))

    def test_create_temp_node_creates_partial_action(self):
        deadline = Decimal("1.6")
        model = ModelBuilder().with_agent("agent", at="start_node") \
            .with_edge("start_node", "end_node", distance=ZERO).model
        expected = action.Move(self.move.start_time, Decimal("0.6"), "agent",
            "start_node", "temp-agent-start_node-end_node", True)

        actual = self.move.create_temp_node(model, deadline)

        assert_that(actual, equal_to(expected))

    def test_create_temp_node_applies_partial_move(self):
        deadline = Decimal("1.6")
        model = ModelBuilder().with_agent("agent", at="start_node")\
            .with_edge("start_node", "end_node", distance=self.move.duration).model
        temp_node = "temp-agent-start_node-end_node"

        self.move.create_temp_node(model, deadline)

        assert_that(model, has_agent("agent").at(temp_node))
        assert_that(model, has_edge().with_distance(deadline - self.move.start_time)
            .from_(temp_node).to(self.move.start_node))
        assert_that(model, has_edge().with_distance(as_start_time(self.move.end_time) - deadline)
            .from_(temp_node).to(self.move.end_node))

    def test_modify_temp_node_creates_partial_move(self):
        object.__setattr__(self.move, "start_node", "temp_node")
        deadline = Decimal("1.6")
        model = ModelBuilder().with_agent("agent", at="temp_node") \
            .with_edge("temp_node", "start_node", Decimal(12)) \
            .with_edge("temp_node", "end_node", Decimal(15)).model

        expected = action.Move(self.move.start_time, Decimal("0.6"), "agent",
            "temp_node", "end_node", True)

        actual = self.move.modify_temp_node(model, deadline)

        assert_that(actual, equal_to(expected))

    def test_modify_temp_node_applies_partial_move_forward(self):
        object.__setattr__(self.move, "start_node", "temp_node")
        deadline = Decimal("1.6")
        to_start = Decimal(12)
        to_end = Decimal(15)
        model = ModelBuilder().with_agent("agent", at="temp_node") \
            .with_edge("temp_node", "start_node", to_start) \
            .with_edge("temp_node", "end_node", to_end).model

        self.move.modify_temp_node(model, deadline)

        movement = deadline - self.move.start_time
        assert_that(model, has_agent("agent").at("temp_node"))
        assert_that(model, has_edge().with_distance(to_start + movement).from_("temp_node").to("start_node"))
        assert_that(model, has_edge().with_distance(to_end - movement).from_("temp_node").to("end_node"))

    def test_modify_temp_node_applies_partial_move_backward(self):
        object.__setattr__(self.move, "start_node", "temp_node")
        object.__setattr__(self.move, "end_node", "start_node")
        deadline = Decimal("1.6")
        to_start = Decimal(12)
        to_end = Decimal(15)
        model = ModelBuilder().with_agent("agent", at="temp_node") \
            .with_edge("temp_node", "start_node", to_start) \
            .with_edge("temp_node", "end_node", to_end).model

        self.move.modify_temp_node(model, deadline)

        movement = deadline - self.move.start_time
        assert_that(model, has_agent("agent").at("temp_node"))
        assert_that(model, has_edge().with_distance(to_start - movement).from_("temp_node").to("start_node"))
        assert_that(model, has_edge().with_distance(to_end + movement).from_("temp_node").to("end_node"))

    @patch("action.Move.create_temp_node")
    @patch("action.Move.is_applicable", new=Mock(return_value=True))
    def test_partially_apply_selects_create(self, create_temp_node):
        expected = False
        deadline = object()

        model = ModelBuilder().with_node("node").model

        actual = self.move.partially_apply(model, deadline)

        self.move.is_applicable.assert_called_once_with(model)
        self.move.create_temp_node.assert_called_once_with(model, deadline)
        assert_that(actual, equal_to(expected))

    @patch("action.Move.modify_temp_node", new=Mock(name="modify_temp_node"))
    @patch("action.Move.create_temp_node", new=Mock(name="create_temp_node"))
    @patch("action.Move.is_applicable", new=Mock(return_value=True))
    def test_partially_apply_selects_modify(self):
        expected = False
        deadline = Mock()
        model = Mock()
        object.__setattr__(self.move, "start_node", "temp_node")

        actual = self.move.partially_apply(model, deadline)

        self.move.is_applicable.assert_called_once_with(model)
        self.move.modify_temp_node.assert_called_once_with(model, deadline)
        assert_that(actual, equal_to(expected))


class ObserveTest(unittest.TestCase):

    def setUp(self):
        self.observe = action.Observe(Decimal(1), "agent", "node")

    def test_is_applicable(self):
        model = ModelBuilder().with_agent("agent", at="node").model
        actual = self.observe.is_applicable(model)
        assert_that(actual)

    def test_is_not_applicable(self):
        model = ModelBuilder().with_agent("agent", at="elsewhere").model
        actual = self.observe.is_applicable(model)
        assert_that(is_not(actual))

    def test_check_new_knowledge_is_true(self):
        unknown_values = {"key": {"actual": ZERO}}
        assumed_values = {"key": 1}

        actual = self.observe._check_new_knowledge(unknown_values, assumed_values)

        assert_that(actual)

    def test_check_new_knowledge_is_false(self):
        unknown_values = {"key": {"actual": ZERO}}
        assumed_values = {"key": ZERO}

        actual = self.observe._check_new_knowledge(unknown_values, assumed_values)

        assert_that(is_not(actual))

    @patch("action.Observe._get_actual_value", new=Mock(side_effect=lambda x: x))
    @patch("action.Observe.is_applicable", new=Mock(return_value=True))
    @patch("action.Observe._check_new_knowledge", new=Mock(return_value=True))
    def test_apply_with_new_knowledge(self):
        unknown = {"k": "v"}
        known = {}
        model = ModelBuilder().with_assumed_values().with_node("node", unknown=unknown, known=known).model

        actual = self.observe.apply(model)

        assert_that(model, has_node("node").with_value(known={"k": "v"}, unknown={}))
        assert_that(actual)

    @patch("action.Observe._get_actual_value", new=Mock(side_effect=lambda x: x))
    @patch("action.Observe.is_applicable", new=Mock(return_value=True))
    @patch("action.Observe._check_new_knowledge", new=Mock(return_value=True))
    def test_apply_with_no_new_knowledge(self):
        unknown = {}
        known = {"k": "v"}
        model = ModelBuilder().with_node("node", unknown=unknown, known=known).model

        actual = self.observe.apply(model)

        assert_that(model, has_node("node").with_value(known={"k": "v"}, unknown={}))
        assert_that(is_not(actual))

    @patch("action.Observe.is_applicable", new=Mock(return_value=True))
    def test_apply_with_no_unknown(self):
        model = ModelBuilder().with_node("node").model

        actual = self.observe.apply(model)

        assert_that(is_not(actual))


class CleanTest(unittest.TestCase):

    def setUp(self):
        self.clean = action.Clean(Decimal(ZERO), Decimal(1), "agent", "room")

    def test_is_applicable(self):
        model = ModelBuilder().with_agent("agent", at="room") \
            .with_node("room", known={"dirty": True, "extra-dirty": False}).model

        actual = self.clean.is_applicable(model)

        assert_that(actual)

    def test_is_not_applicable_because_agent_elsewhere(self):
        model = ModelBuilder().with_agent("agent", at="elsewhere") \
            .with_node("room", known={"extra-dirty": False}).model

        actual = self.clean.is_applicable(model)

        assert_that(is_not(actual))

    def test_is_not_applicable_because_extra_dirty(self):
        model = ModelBuilder().with_agent("agent", at="room") \
            .with_node("room", known={"extra-dirty": True}).model

        actual = self.clean.is_applicable(model)

        assert_that(is_not(actual))

    def test_is_not_applicable_because_extra_dirty_is_assumed_if_not_known(self):
        model = ModelBuilder().with_agent("agent", at="room").with_node("room").model

        actual = self.clean.is_applicable(model)

        assert_that(is_not(actual))

    def test_apply(self):
        node_value = MagicMock()
        model = ModelBuilder().with_node("room", value=node_value).model
        object.__setattr__(self.clean, "is_applicable", Mock(return_value=True))

        actual = self.clean.apply(model)

        node_value.__getitem__.assert_called_once_with("known")
        known_values = node_value["known"]
        known_values.__delitem__.assert_called_once("dirty")
        known_values.__delitem__.assert_called_once("dirtiness")
        known_values.__setitem__.assert_called_once_with("cleaned", ANY)
        assert_that(is_not(actual))

    @patch("action.Clean.is_applicable", new=Mock(return_value=True))
    def test_partially_apply(self):
        deadline = Decimal("0.6")
        duration = deadline - self.clean.start_time
        node_value = MagicMock(name="node")
        node_value.__getitem__().__getitem__.return_value = deadline + 1
        model = ModelBuilder().with_node("room", value=node_value).model

        expected = False

        actual = self.clean.partially_apply(model, deadline)

        node_value.__getitem__.assert_called_with("known")
        node_value["known"].__setitem__.assert_called_once("dirtiness", duration)
        assert_that(actual, equal_to(expected))


class ExtraCleanTest(unittest.TestCase):

    def setUp(self):
        self.extra_clean = action.ExtraClean(Decimal(ZERO), Decimal(1), "agent0", "agent1", "room")

    def test_is_applicable(self):
        model = ModelBuilder().with_agent("agent0", at="room") \
            .with_agent("agent1", at="room") \
            .with_node("room", known={"dirty": False, "extra-dirty": True}).model

        actual = self.extra_clean.is_applicable(model)

        assert_that(actual)

    def test_is_not_applicable_because_agent_elsewhere(self):
        model = ModelBuilder().with_agent("agent0", at="elsewhere") \
            .with_agent("agent1", at="elsewhere") \
            .with_node("room", known={"dirty": False, "extra-dirty": True}).model

        actual = self.extra_clean.is_applicable(model)

        assert_that(is_not(actual))

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

        assert_that(is_not(actual))

    @patch("action.ExtraClean.is_applicable", new=Mock(return_value=True))
    def test_apply(self):
        node_value = MagicMock()
        model = ModelBuilder().with_node("room", value=node_value).model

        actual = self.extra_clean.apply(model)

        node_value.__getitem__.assert_called_once_with("known")
        known_values = node_value["known"]
        known_values.__delitem__.assert_called_once("extra-dirty")
        known_values.__delitem__.assert_called_once("dirtiness")
        known_values.__setitem__.assert_called_once_with("cleaned", ANY)
        assert_that(is_not(actual))

    @patch("action.ExtraClean.is_applicable", new=Mock(return_value=True))
    def test_partially_apply(self):
        deadline = Decimal("0.6")
        duration = deadline - self.extra_clean.start_time
        node_value = MagicMock(name="node")
        node_value.__getitem__().__getitem__.return_value = deadline + 1
        model = ModelBuilder().with_node("room", value=node_value).model

        expected = False

        actual = self.extra_clean.partially_apply(model, deadline)

        node_value.__getitem__.assert_called_with("known")
        node_value["known"].__setitem__.assert_called_once("dirtiness", duration)
        assert_that(actual, equal_to(expected))


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()