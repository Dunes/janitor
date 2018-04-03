__author__ = 'jack'

from unittest import TestCase

from decimal import Decimal
from accuracy import as_start_time

from unittest.mock import Mock, patch
from hamcrest import assert_that, is_not, has_entry, equal_to, empty, has_key, is_
from util.roborescue.matchers import has_agent, has_edge, has_node, has_object
from util.roborescue.builder import ModelBuilder, ActionBuilder

from markettaskallocation.common.problem_encoder import find_object

from markettaskallocation.roborescue import Move, Observe


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
            .with_edge(start, end, distance=50, known=True) \
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

    def test_apply(self):
        # given
        agent = "police1"
        start = "building1"
        end = "hospital1"
        model = ModelBuilder().with_agent(agent, at=start) \
            .with_edge(start, end, distance=50, type="edge", known=True) \
            .model
        move = ActionBuilder().agent(agent).start_node(start).end_node(end).move()

        # when
        actual = move.apply(model)

        # then
        self.assertFalse(actual)
        assert_that(model["objects"], has_agent(agent).at(end))
        assert_that(model["objects"], is_not(has_agent(agent).at(start)))

    def test_apply_when_moving_from_temp_node(self):
        object.__setattr__(self.move, "start_node", "temp_start_node")
        distance = 1
        model = ModelBuilder().with_agent("agent", at="temp_start_node") \
            .with_edge("temp_start_node", "end_node", distance=distance) \
            .with_edge("end_node", "other_node", distance=distance).model

        self.move.apply(model)

        assert_that(model["objects"], has_agent("agent").at("end_node"))
        assert_that(model["objects"], is_not(has_agent("agent").at("temp_start_node")))
        assert_that(model["objects"], is_not(has_object("temp_start_node")))
        assert_that(model["graph"]["edges"], is_not(has_key("temp_start_node end_node")))

    def test_create_temp_node_applies_partial_move(self):
        deadline = Decimal("1.6")
        model = ModelBuilder().with_agent("agent", at="start_node")\
            .with_edge("start_node", "end_node", distance=self.move.duration).model
        temp_node = "temp-agent-start_node-end_node"

        self.move.create_temp_node(model, deadline)

        assert_that(model["objects"], has_agent("agent").at(temp_node))
        assert_that(model["graph"]["edges"], has_edge().with_distance(deadline - self.move.start_time)
            .from_(temp_node).to(self.move.start_node))
        assert_that(model["graph"]["edges"], has_edge().with_distance(as_start_time(self.move.end_time) - deadline)
            .from_(temp_node).to(self.move.end_node))

    def test_modify_temp_node_applies_partial_move_forward(self):
        object.__setattr__(self.move, "start_node", "temp_node")
        deadline = Decimal(20)
        to_start = Decimal(100)
        to_end = Decimal(50)
        model = ModelBuilder().with_agent("agent", at="temp_node") \
            .with_edge("temp_node", "start_node", to_start) \
            .with_edge("temp_node", "end_node", to_end).model

        self.move.modify_temp_node(model, deadline)

        movement = deadline - self.move.start_time
        assert_that(model["objects"], has_agent("agent").at("temp_node"))
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
        assert_that(model["objects"], has_agent("agent").at("temp_node"))
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

        self.move.modify_temp_node.assert_called_once_with(model, deadline)
        assert_that(actual, equal_to(expected))

    def test_partial_move_when_edge_becomes_blocked_and_less_than_half_moved(self):
        # given
        agent = "agent1"
        node = "building1"
        other_node = "building2"
        start_time = ZERO
        distance = Decimal(10)
        model = ModelBuilder() \
            .with_agent(agent, at=node) \
            .with_node(node, type="building") \
            .with_node(other_node, type="building") \
            .with_edge(node, other_node, distance=distance, blockedness=20) \
            .model
        move = Move(start_time, distance, agent, node, other_node).as_partial(end_time=Decimal(4))

        # when
        move.apply(model)

        # then
        temp_node_id = "temp-{}-{}-{}".format(agent, node, other_node)
        assert_that(find_object(agent, model["objects"])["at"][1], equal_to(temp_node_id))
        assert_that(model["objects"], has_object(temp_node_id))
        assert_that(model["graph"]["edges"], has_edge(temp_node_id, node))
        assert_that(model["graph"]["edges"], is_not(has_edge(temp_node_id, other_node)))

    def test_partial_move_when_edge_becomes_blocked_and_more_than_half_moved(self):
        # given
        agent = "agent1"
        node = "building1"
        other_node = "building2"
        start_time = ZERO
        distance = Decimal(10)
        model = ModelBuilder() \
            .with_agent(agent, at=node) \
            .with_node(node, type="building") \
            .with_node(other_node, type="building") \
            .with_edge(node, other_node, distance=distance, blockedness=20) \
            .model
        move = Move(start_time, distance, agent, node, other_node).as_partial(end_time=Decimal(6))

        # when
        move.apply(model)

        # then
        temp_node_id = "temp-{}-{}-{}".format(agent, node, other_node)
        assert_that(find_object(agent, model["objects"])["at"][1], equal_to(temp_node_id))
        assert_that(model["objects"], has_object(temp_node_id))
        assert_that(model["graph"]["edges"], has_edge(temp_node_id, other_node))
        assert_that(model["graph"]["edges"], is_not(has_edge(temp_node_id, node)))


class TestUnblock(TestCase):

    def test_is_applicable_when_at_node(self):
        # given
        agent = "police1"
        start = "building1"
        end = "building2"
        model = ModelBuilder().with_agent(agent, at=start) \
            .with_edge(start, end, distance=50, blockedness=10, known=True) \
            .model
        unblock = ActionBuilder().agent(agent).start_node(start).end_node(end).unblock()

        # when
        actual = unblock.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_applicable_when_at_other_node(self):
        # given
        agent = "police1"
        start = "building1"
        end = "building2"
        model = ModelBuilder().with_agent(agent, at=end) \
            .with_edge(start, end, distance=50, blockedness=10, known=True) \
            .model
        unblock = ActionBuilder().agent(agent).start_node(start).end_node(end).unblock()

        # when
        actual = unblock.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_at_wrong_node(self):
        # given
        agent = "police1"
        other = "other1"
        start = "building1"
        end = "building2"
        model = ModelBuilder().with_agent(agent, at=other) \
            .with_edge(start, end, distance=50, blockedness=10, known=True) \
            .model
        unblock = ActionBuilder().agent(agent).start_node(start).end_node(end).unblock()

        # when
        actual = unblock.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_if_police(self):
        # given
        agent = "agent1"
        start = "building1"
        end = "building2"
        model = ModelBuilder().with_agent(agent, type="police", at=start) \
            .with_edge(start, end, distance=50, blockedness=10, known=True) \
            .model
        unblock = ActionBuilder().agent(agent).start_node(start).end_node(end).unblock()

        # when
        actual = unblock.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_if_medic(self):
        # given
        agent = "medic1"
        start = "building1"
        end = "building2"
        model = ModelBuilder().with_agent(agent, type="medic", at=start) \
            .with_agent("police1") \
            .with_edge(start, end, distance=50, blockedness=10, known=True) \
            .model
        unblock = ActionBuilder().agent(agent).start_node(start).end_node(end).unblock()

        # when
        actual = unblock.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_when_blocked(self):
        # given
        agent = "police1"
        start = "building1"
        end = "building2"
        model = ModelBuilder().with_agent(agent, at=start) \
            .with_edge(start, end, distance=50, blockedness=10, known=True) \
            .model
        unblock = ActionBuilder().agent(agent).start_node(start).end_node(end).unblock()

        # when
        actual = unblock.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_unblocked(self):
        # given
        agent = "police1"
        start = "building1"
        end = "building2"
        model = ModelBuilder().with_agent(agent, at=start) \
            .with_edge(start, end, distance=50, type="edge", known=True) \
            .model
        unblock = ActionBuilder().agent(agent).start_node(start).end_node(end).unblock()

        # when
        actual = unblock.is_applicable(model)

        # then

        self.assertFalse(actual)

    def test_apply(self):
        # given
        agent = "police1"
        start = "building1"
        end = "building2"
        blockedness = 20
        model = ModelBuilder().with_agent(agent, at=start) \
            .with_edge(start, end, distance=50, blockedness=blockedness, known=True) \
            .model
        unblock = ActionBuilder().agent(agent).start_node(start).end_node(end) \
            .duration(blockedness).unblock()

        # when
        unblock.apply(model)

        # then
        assert_that(model["graph"]["edges"], has_edge(start, end).unblocked())
        assert_that(model["graph"]["edges"], has_edge(end, start).unblocked())

    def test_partially_apply(self):
        # given
        agent = "police1"
        start = "building1"
        end = "building2"
        blockedness = 20
        duration = blockedness
        partial_end_time = duration // 2
        model = ModelBuilder().with_agent(agent, at=start) \
            .with_edge(start, end, distance=50, blockedness=blockedness, known=True) \
            .model
        unblock = ActionBuilder().agent(agent).start_node(start).end_node(end) \
            .start_time().end_time(duration) \
            .unblock().as_partial(end_time=partial_end_time)

        # when
        unblock.apply(model)

        # then
        assert_that(model["graph"]["edges"], has_edge(start, end).blocked(blockedness - partial_end_time))
        assert_that(model["graph"]["edges"], has_edge(end, start).blocked(blockedness - partial_end_time))


class TestLoad(TestCase):

    def test_is_applicable_when_at_node(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True) \
            .with_object(target, at=node) \
            .model
        load = ActionBuilder().agent(agent).node(node).target(target).load()

        # when
        actual = load.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_at_wrong_node(self):
        # given
        agent = "medic1"
        node = "building1"
        other = "other1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=other, available=True) \
            .with_object(target, at=node) \
            .model
        load = ActionBuilder().agent(agent).node(node).target(target).load()

        # when
        actual = load.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_when_target_present(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True) \
            .with_object(target, at=node) \
            .model
        load = ActionBuilder().agent(agent).node(node).target(target).load()

        # when
        actual = load.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_target_not_present(self):
        # given
        agent = "medic1"
        node = "building1"
        other = "other1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True) \
            .with_object(target, at=other) \
            .model
        load = ActionBuilder().agent(agent).node(node).target(target).load()

        # when
        actual = load.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_when_medic(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True) \
            .with_object(target, at=node) \
            .model
        load = ActionBuilder().agent(agent).node(node).target(target).load()

        # when
        actual = load.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_not_medic(self):
        # given
        agent = "police1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, type="police") \
            .with_agent("medic1", type="medic") \
            .with_object(target, at=node) \
            .model
        load = ActionBuilder().agent(agent).node(node).target(target).load()

        # when
        actual = load.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_when_available(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True) \
            .with_object(target, at=node) \
            .model
        load = ActionBuilder().agent(agent).node(node).target(target).load()

        # when
        actual = load.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_unavailable(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=False) \
            .with_object(target, at=node) \
            .model
        load = ActionBuilder().agent(agent).node(node).target(target).load()

        # when
        actual = load.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_not_applicable_when_carrying(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True, carrying="civilian2") \
            .with_object(target, at=node) \
            .model
        load = ActionBuilder().agent(agent).node(node).target(target).load()

        # when
        actual = load.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_not_applicable_when_target_not_at_somewhere(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=False) \
            .with_object(target) \
            .model
        load = ActionBuilder().agent(agent).node(node).target(target).load()

        # when
        actual = load.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_apply(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True, empty=True) \
            .with_object(target, at=node) \
            .model
        load = ActionBuilder().agent(agent).node(node).target(target).load()

        # when
        load.apply(model)

        # then
        assert_that(model["objects"], has_agent(agent).available(True))
        assert_that(model["objects"], has_agent(agent).carrying(target))
        assert_that(find_object(agent, model["objects"]), is_not(has_key("empty")))
        assert_that(find_object(target, model["objects"])["known"], is_not(has_key("at")))

    def test_partially_apply(self):
        # given
        load = ActionBuilder().load()

        # when
        actual = load.as_partial()

        # then
        assert_that(load, equal_to(actual))


class TestUnload(TestCase):

    def test_is_applicable_when_at_node(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True, carrying=target) \
            .with_object(target) \
            .model
        unload = ActionBuilder().agent(agent).node(node).target(target).unload()

        # when
        actual = unload.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_at_wrong_node(self):
        # given
        agent = "medic1"
        node = "building1"
        other = "other1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=other, available=True, carrying=target) \
            .with_object(target) \
            .model
        unload = ActionBuilder().agent(agent).node(node).target(target).unload()

        # when
        actual = unload.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_when_carrying(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True, carrying=target) \
            .with_object(target) \
            .model
        unload = ActionBuilder().agent(agent).node(node).target(target).unload()

        # when
        actual = unload.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_not_carrying(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True, empty=True) \
            .with_object(target, at=node) \
            .model
        unload = ActionBuilder().agent(agent).node(node).target(target).unload()

        # when
        actual = unload.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_not_applicable_when_carrying_different_object(self):
        # given
        agent = "medic1"
        node = "building1"
        other = "civilian2"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True, carrying=other) \
            .with_object(target).with_object(other) \
            .model
        unload = ActionBuilder().agent(agent).node(node).target(target).unload()

        # when
        actual = unload.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_when_medic(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True, carrying=target) \
            .with_object(target) \
            .model
        unload = ActionBuilder().agent(agent).node(node).target(target).unload()

        # when
        actual = unload.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_not_medic(self):
        # given
        agent = "police1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, type="police") \
            .with_agent("medic1", type="medic") \
            .with_object(target) \
            .model
        unload = ActionBuilder().agent(agent).node(node).target(target).unload()

        # when
        actual = unload.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_when_available(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True, carrying=target) \
            .with_object(target) \
            .model
        unload = ActionBuilder().agent(agent).node(node).target(target).unload()

        # when
        actual = unload.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_unavailable(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=False) \
            .with_object(target, at=node) \
            .model
        unload = ActionBuilder().agent(agent).node(node).target(target).unload()

        # when
        actual = unload.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_apply(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True, carrying=target) \
            .with_object(target) \
            .model
        unload = ActionBuilder().agent(agent).node(node).target(target).unload()

        # when
        unload.apply(model)

        # then
        assert_that(model["objects"], has_agent(agent).available(True))
        assert_that(model["objects"], has_agent(agent).empty(True))
        assert_that(find_object(agent, model["objects"]), is_not(has_key("carrying")))
        target_object = find_object(target, model["objects"])["known"]
        assert_that(target_object, has_key("at"))
        assert_that(target_object["at"], equal_to([True, node]))

    def test_partially_apply(self):
        # given
        unload = ActionBuilder().unload()

        # when
        actual = unload.as_partial()

        # then
        assert_that(unload, equal_to(actual))


class TestRescue(TestCase):

    def test_is_applicable_when_at_node(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True) \
            .with_object(target, at=node, buried=True) \
            .model
        rescue = ActionBuilder().agent(agent).node(node).target(target).rescue()

        # when
        actual = rescue.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_at_wrong_node(self):
        # given
        agent = "medic1"
        other = "other1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=other, available=True) \
            .with_object(target, at=node, buried=True) \
            .model
        rescue = ActionBuilder().agent(agent).node(node).target(target).rescue()

        # when
        actual = rescue.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_if_medic(self):
        # given
        agent = "agent1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, type="medic", at=node, available=True) \
            .with_object(target, at=node, buried=True) \
            .model
        rescue = ActionBuilder().agent(agent).node(node).target(target).rescue()

        # when
        actual = rescue.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_if_medic(self):
        # given
        agent = "police1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, type="police", at=node, available=True) \
            .with_agent("medic1") \
            .with_object(target, at=node, buried=True) \
            .model
        rescue = ActionBuilder().agent(agent).node(node).target(target).rescue()

        # when
        actual = rescue.is_applicable(model)

        # then
        self.assertFalse(actual)

    def test_is_applicable_when_buried(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True) \
            .with_object(target, at=node, buried=True) \
            .model
        rescue = ActionBuilder().agent(agent).node(node).target(target).rescue()

        # when
        actual = rescue.is_applicable(model)

        # then
        self.assertTrue(actual)

    def test_is_not_applicable_when_not_buried(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=True) \
            .with_object(target, at=node, buried=False) \
            .model
        rescue = ActionBuilder().agent(agent).node(node).target(target).rescue()

        # when
        actual = rescue.is_applicable(model)

        # then

        self.assertFalse(actual)

    def test_is_not_applicable_when_not_available(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        model = ModelBuilder().with_agent(agent, at=node, available=False) \
            .with_object(target, at=node, buried=True) \
            .model
        rescue = ActionBuilder().agent(agent).node(node).target(target).rescue()

        # when
        actual = rescue.is_applicable(model)

        # then

        self.assertFalse(actual)

    def test_apply(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        buriednesss = 10
        model = ModelBuilder().with_agent(agent, at=node, available=True) \
            .with_object(target, at=node, buried=True, buriedness=buriednesss) \
            .model

        rescue = ActionBuilder().agent(agent).node(node).target(target).rescue()

        # when
        rescue.apply(model)

        # then
        target_object = (find_object(target, model["objects"])["known"])
        assert_that(target_object, has_key("unburied"))
        assert_that(target_object["unburied"], equal_to(True))
        assert_that(target_object, is_not(has_key("buried")))
        assert_that(target_object, is_not(has_key("buriedness")))

    def test_partially_apply(self):
        # given
        agent = "medic1"
        node = "building1"
        target = "civilian1"
        buriednesss = 10
        duration = buriednesss
        partial_end_time = duration // 2
        model = ModelBuilder().with_agent(agent, at=node, available=True) \
            .with_object(target, at=node, buried=True, buriedness=buriednesss) \
            .model
        rescue = ActionBuilder().agent(agent).node(node).target(target) \
            .start_time().end_time(duration) \
            .rescue().as_partial(end_time=partial_end_time)

        # when
        rescue.apply(model)

        # then
        target_object = (find_object(target, model["objects"])["known"])
        assert_that(target_object, has_key("buried"))
        assert_that(target_object["buried"], equal_to(True))
        assert_that(target_object["buriedness"], equal_to(buriednesss - partial_end_time))


class ObserveTest(TestCase):

    def setUp(self):
        self.observe = Observe(Decimal(1), "agent", "node")

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

    @patch("roborescue.action.Observe._get_actual_value", new=Mock(side_effect=lambda x: x))
    @patch("roborescue.action.Observe.is_applicable", new=Mock(return_value=True))
    @patch("roborescue.action.Observe._check_new_knowledge", new=Mock(return_value=True))
    def test_apply_with_new_knowledge(self):
        node = "node"
        unknown = {"k": "v"}
        known = {"at": [True, node]}
        model = ModelBuilder().with_assumed_values().with_node(node, unknown=unknown, known=known).model

        actual = self.observe.apply(model)

        assert_that(actual, equal_to([node]))
        node = find_object(node, model["objects"])
        assert_that(node["known"], has_entry("k", "v"))
        assert_that(node["known"], has_entry("k", "v"))
        assert_that(node["unknown"], is_(empty()))

    @patch("roborescue.action.Observe._get_actual_value", new=Mock(side_effect=lambda x: x))
    @patch("roborescue.action.Observe.is_applicable", new=Mock(return_value=True))
    @patch("roborescue.action.Observe._check_new_knowledge", new=Mock(return_value=True))
    def test_apply_with_no_new_knowledge(self):
        unknown = {}
        known = {"k": "v"}
        model = ModelBuilder().with_node("node", unknown=unknown, known=known).model

        actual = self.observe.apply(model)

        assert_that(model["objects"], has_node("node").with_value(known={"k": "v"}, unknown={}))
        assert_that(is_not(actual))

    @patch("roborescue.action.Observe.is_applicable", new=Mock(return_value=True))
    def test_apply_with_no_unknown(self):
        model = ModelBuilder().with_node("node").model

        actual = self.observe.apply(model)

        assert_that(is_not(actual))

    def test_apply_observes_all_objects_at_node(self):
        # given
        agent = "agent1"
        node = "building1"
        other_node = "building2"
        observable1 = "civilian1"
        observable2 = "civilian2"
        model = ModelBuilder(assumed_values={"buried": object()}).with_agent(agent, at=node) \
            .with_node(node) \
            .with_object(observable1, at=node, buried={"actual": True}, known=False) \
            .with_object(observable2, at=other_node, buried={"actual": True}, known=False) \
            .model
        observe = self.observe = Observe(ZERO, agent, node)

        # when
        observe.apply(model)

        # then
        observable_object = find_object(observable1, model["objects"])
        assert_that(observable_object["unknown"], is_(empty()))
        assert_that(observable_object["known"], has_entry("buried", True))
        assert_that(observable_object["known"], has_entry("at", [True, node]))
        observable_object2 = find_object(observable2, model["objects"])
        assert_that(observable_object2["unknown"], is_not(empty()))
        assert_that(observable_object2["unknown"], has_entry("buried", {"actual": True}))
        assert_that(observable_object2["known"], has_entry("at", [True, other_node]))

    def test_apply_observes_blocked_edges_next_to_node(self):
        # given
        agent = "agent1"
        node = "building1"
        other_node = "building2"
        model = ModelBuilder(assumed_values={"blockedness": 0, "blocked-edge": False, "edge": True}) \
            .with_agent(agent, at=node) \
            .with_edge(node, other_node, distance=10, blockedness=20, known=False) \
            .model
        observe = self.observe = Observe(ZERO, agent, node)

        # when
        observe.apply(model)

        # then
        edge_id = node + " " + other_node
        edge = model["graph"]["edges"][edge_id]
        assert_that(edge["unknown"], is_(empty()))
        assert_that(edge["known"], has_entry("blocked-edge", True))
        assert_that(edge["known"], has_entry("blockedness", 20))

        edge_id = other_node + " " + node
        edge = model["graph"]["edges"][edge_id]
        assert_that(edge["unknown"], is_(empty()))
        assert_that(edge["known"], has_entry("blocked-edge", True))
        assert_that(edge["known"], has_entry("blockedness", 20))
