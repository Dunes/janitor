__author__ = 'jack'

from unittest import TestCase, skip

from decimal import Decimal
from accuracy import as_start_time, as_end_time

from unittest.mock import Mock, patch
from hamcrest import assert_that, is_not, has_item, equal_to, greater_than, has_key
from util.roborescue.matchers import has_agent, has_edge, has_node, has_object
from util.roborescue.builder import ModelBuilder, ActionBuilder

from roborescue.action import Move, Unblock, Load, Unload, Rescue


ZERO = Decimal(0)


class TestMove(TestCase):

    def setUp(self):
        self.move = Move(Decimal(1), Decimal(2), "agent", "start_node", "end_node")

    def test_is_applicable_when_at_right_node(self):
        # given
        agent = "police1"
        start = "building1"
        end = "hospital1"
        model = ModelBuilder().with_agent(agent, at=start) \
            .with_edge(start, end, distance=50, blockedness=0, known=True) \
            .model
        move = ActionBuilder().agent(agent).start_node(start).end_node(end).move()

        # when
        actual = move.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_applicable_when_at_wrong_node(self):
        # given
        move = ActionBuilder().agent().move()
        model = ModelBuilder().with_agent(move.agent, at="another_node") \
            .model

        # when
        actual = move.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_when_blocked(self):
        # given
        start = "building1"
        end = "hospital1"
        move = ActionBuilder().agent().start_node(start).end_node(end).move()
        model = ModelBuilder().with_agent(move.agent, at=start) \
            .with_edge(start, end, distance=50, blockedness=10, known=True) \
            .model

        # when
        actual = move.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_when_blocked_and_unknown(self):
        # given
        start = "building1"
        end = "hospital1"
        move = ActionBuilder().agent().start_node(start).end_node(end).move()
        model = ModelBuilder().with_agent(move.agent, at=start) \
            .with_edge(start, end, distance=50, blockedness=10, known=False) \
            .model

        # when
        actual = move.is_applicable(model)

        # then
        self.assertFalse(actual)

    @skip
    def test_apply(self):
        # given
        agent = "police1"
        start = "building1"
        end = "hospital1"
        model = ModelBuilder().with_agent(agent, at=start) \
            .with_edge(start, end, distance=50, blockedness=0, known=True) \
            .model
        move = ActionBuilder().agent(agent).start_node(start).end_node(end).move()

        # when
        actual = move.apply(model)

        # then
        self.assertTrue(actual)
        self.fail()

    def test_apply_when_moving_from_temp_node(self):
        object.__setattr__(self.move, "start_node", "temp_start_node")
        distance = 1
        model = ModelBuilder().with_agent("agent", at="temp_start_node") \
            .with_edge("temp_start_node", "end_node", distance=distance, blockedness=0) \
            .with_edge("end_node", "other_node", distance=distance, blockedness=0).model

        self.move.apply(model)

        assert_that(model, has_agent("agent").at("end_node"))
        assert_that(model, has_agent("agent").at("end_node"))
        assert_that(model["objects"], is_not(has_object("temp_start_node")))
        assert_that(model["graph"]["edges"], is_not(has_key("temp_start_node end_node")))

    def test_create_temp_node_creates_partial_action(self):
        deadline = Decimal("1.6")
        model = ModelBuilder().with_agent("agent", at="start_node") \
            .with_edge("start_node", "end_node", distance=ZERO).model
        expected = Move(self.move.start_time, Decimal("0.6"), "agent",
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
        assert_that(model["graph"]["edges"], has_edge().with_distance(deadline - self.move.start_time)
            .from_(temp_node).to(self.move.start_node))
        assert_that(model["graph"]["edges"], has_edge().with_distance(as_start_time(self.move.end_time) - deadline)
            .from_(temp_node).to(self.move.end_node))

    def test_modify_temp_node_creates_partial_move(self):
        object.__setattr__(self.move, "start_node", "temp_node")
        deadline = Decimal("1.6")
        model = ModelBuilder().with_agent("agent", at="temp_node") \
            .with_edge("temp_node", "start_node", Decimal(12)) \
            .with_edge("temp_node", "end_node", Decimal(15)).model

        expected = Move(self.move.start_time, Decimal("0.6"), "agent",
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
        assert_that(model["graph"]["edges"], has_edge().with_distance(to_start + movement).from_("temp_node")
            .to("start_node"))
        assert_that(model["graph"]["edges"], has_edge().with_distance(to_end - movement).from_("temp_node")
            .to("end_node"))

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
        assert_that(model["graph"]["edges"], has_edge().with_distance(to_start - movement).from_("temp_node")
            .to("start_node"))
        assert_that(model["graph"]["edges"], has_edge().with_distance(to_end + movement).from_("temp_node")
            .to("end_node"))

    @patch("roborescue.action.Move.create_temp_node")
    @patch("roborescue.action.Move.is_applicable", new=Mock(return_value=True))
    def test_partially_apply_selects_create(self, create_temp_node):
        expected = False
        deadline = object()

        model = ModelBuilder().with_node("node").model

        actual = self.move.partially_apply(model, deadline)

        self.move.is_applicable.assert_called_once_with(model)
        self.move.create_temp_node.assert_called_once_with(model, deadline)
        assert_that(actual, equal_to(expected))

    @patch("roborescue.action.Move.modify_temp_node", new=Mock(name="modify_temp_node"))
    @patch("roborescue.action.Move.create_temp_node", new=Mock(name="create_temp_node"))
    @patch("roborescue.action.Move.is_applicable", new=Mock(return_value=True))
    def test_partially_apply_selects_modify(self):
        expected = False
        deadline = Mock()
        model = Mock()
        object.__setattr__(self.move, "start_node", "temp_node")

        actual = self.move.partially_apply(model, deadline)

        self.move.is_applicable.assert_called_once_with(model)
        self.move.modify_temp_node.assert_called_once_with(model, deadline)
        assert_that(actual, equal_to(expected))