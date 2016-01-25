from unittest import TestCase
from hamcrest import assert_that, equal_to
from io import StringIO
from collections import OrderedDict
from decimal import Decimal

from util.roborescue import make_bidirectional

from roborescue.problem_encoder import (encode_objects, encode_init, encode_graph, collate_objects, encode_goal,
                                        encode_metric, create_predicate, collate_object_types, encode_deadlines,
                                        convert_goals)

from roborescue.goal import Goal

__author__ = 'jack'


class ProblemEncoderTest(TestCase):

    def setUp(self):
        self.out = StringIO()

    def test_encode_objects(self):
        # given
        objects = OrderedDict([
            ('building', ['building1']),
            ('civilian', ['civ1', 'civ2']),
            ('hospital', ['hospital1']),
            ('medic', ['medic1']),
            ('police', [])
        ])
        expected = "(:objects building1 - building civ1 civ2 - civilian hospital1 - hospital medic1 - medic )\n"

        # when
        encode_objects(self.out, objects)
        actual = self.out.getvalue()

        # then
        self.assertNotIn("police", actual)
        self.assertEqual(actual, expected)

    def test_encode_values(self):
        # given
        assumed_values = {'blocked': False, 'blockedness': 'min', 'buriedness': 'max'}
        objects = OrderedDict([
            ('civ1', {
                'known': OrderedDict([
                    ('alive', True),
                    ('at', [True, 'building1']),
                    ('buried', True)
                ]),
                'unknown': {'buriedness': {'actual': 50, 'min': 0, 'max': 100}}
            }),
            ('police1', {'at': [True, 'hospital1']})
        ])

        # when
        encode_init(self.out, objects, [], {"edges": {}, "bidirectional": False}, assumed_values)
        actual = self.out.getvalue()

        # then
        expected = "(:init " \
                   "(alive civ1 ) " \
                   "(at civ1 building1 ) " \
                   "(buried civ1 ) " \
                   "(= (buriedness civ1 )  100 ) " \
                   "(at police1 hospital1 ) ) "
        self.assertEqual(expected, actual)

    def test_encode_graph_with_unknown_edge(self):
        # given
        graph = {
            "edges": make_bidirectional(OrderedDict([
                ("building1 hospital1", OrderedDict([
                    ("known", OrderedDict([
                        ("distance", 50),
                        ("edge", True),
                    ])),
                    ("unknown", OrderedDict([
                        ("blockedness", {"max": 100, "min": 0, "actual": 10})
                    ]))
                ]))
            ])),
        }
        assumed_values = {"blocked-edge": False, "blockedness": "max"}

        # when
        encode_graph(self.out, graph, assumed_values)
        actual = self.out.getvalue()

        # then
        expected = "(= (distance building1 hospital1 )  50 ) " \
            + "(edge building1 hospital1 ) " \
            + "(= (blockedness building1 hospital1 )  100 ) " \
            + "(= (distance hospital1 building1 )  50 ) " \
            + "(edge hospital1 building1 ) " \
            + "(= (blockedness hospital1 building1 )  100 ) "
        self.assertEqual(expected, actual)

    def test_encode_graph_with_known_edge(self):
        # given
        graph = {
            "edges": make_bidirectional(OrderedDict([
                ("building1 hospital1", OrderedDict([
                    ("known", OrderedDict([
                        ("distance", 50),
                        ("edge", True),
                    ])),
                    ("unknown", OrderedDict([
                        ("blockedness", {"max": 100, "min": 0, "actual": 10})
                    ]))
                ]))
            ])),
        }
        assumed_values = {"blocked-edge": False, "blockedness": "max"}

        # when
        encode_graph(self.out, graph, assumed_values)
        actual = self.out.getvalue()

        # then
        expected = "(= (distance building1 hospital1 )  50 ) " \
            + "(edge building1 hospital1 ) " \
            + "(= (blockedness building1 hospital1 )  100 ) " \
            + "(= (distance hospital1 building1 )  50 ) " \
            + "(edge hospital1 building1 ) " \
            + "(= (blockedness hospital1 building1 )  100 ) "
        self.assertEqual(expected, actual)

    def test_encode_graph_with_known_blocked_edge(self):
        # given
        graph = {
            "edges": make_bidirectional(OrderedDict([
                ("building1 hospital1", OrderedDict([
                    ("known", OrderedDict([
                        ("distance", 50),
                        ("blocked-edge", True),
                    ])),
                    ("unknown", OrderedDict([
                        ("blockedness", {"max": 100, "min": 0, "actual": 10})
                    ]))
                ]))
            ])),
        }
        assumed_values = {"blocked-edge": False, "blockedness": "max"}

        # when
        encode_graph(self.out, graph, assumed_values)
        actual = self.out.getvalue()

        # then
        expected = "(= (distance building1 hospital1 )  50 ) " \
            "(blocked-edge building1 hospital1 ) " \
            "(= (blockedness building1 hospital1 )  100 ) " \
            "(= (distance hospital1 building1 )  50 ) " \
            "(blocked-edge hospital1 building1 ) " \
            "(= (blockedness hospital1 building1 )  100 ) "
        self.assertEqual(expected, actual)

    def test_collate_objects(self):
        # given
        objects = {
            "medic": {"medic1": "medic1_value"},
            "police": {
                "police1": "police1_value",
                "police2": "police2_value"
            }
        }
        expected = {
            "police1": "police1_value",
            "police2": "police2_value",
            "medic1": "medic1_value",
        }

        # when
        actual = collate_objects(objects, agent="all")

        # then
        self.assertEqual(expected, actual)

    def test_encode_rescued_goal(self):
        # given
        goals = convert_goals([
            Goal(predicate=("rescued", "civ1"), deadline=Decimal("inf")),
            Goal(predicate=("rescued", "civ2"), deadline=Decimal("inf"))],
            False)
        expected = "" \
            "(:goal (and " \
            "(rescued civ1 ) " \
            "(rescued civ2 ) " \
            "))\n"

        # when
        encode_goal(self.out, goals)
        actual = self.out.getvalue()

        # then
        self.assertEqual(expected, actual)

    def test_encode_rescued_preference(self):
        # given
        goals = convert_goals([
            Goal(predicate=("rescued", "civ1"), deadline=Decimal("inf")),
            Goal(predicate=("rescued", "civ2"), deadline=Decimal("inf"))],
            True)
        expected = "" \
            "(:goal (and " \
            "(preference pref-rescued-civ1-Infinity (rescued civ1 )  ) " \
            "(preference pref-rescued-civ2-Infinity (rescued civ2 )  ) " \
            "))\n"

        # when
        encode_goal(self.out, goals)
        actual = self.out.getvalue()

        # then
        assert_that(actual, equal_to(expected))

    def test_encode_edge_preference_with_deadline(self):
        # given
        goals = convert_goals([Goal(predicate=("edge", "x", "y"), deadline=Decimal(0))], True)
        expected = "" \
            "(:goal (and " \
            "(preference pref-cleared-x-y-0 (cleared x y cleared-x-y-0 )  ) " \
            "))\n"

        # when
        encode_goal(self.out, goals)
        actual = self.out.getvalue()

        # then
        self.assertEqual(expected, actual)

    def test_encode_edge_goal_with_deadline(self):
        # given
        goals = convert_goals([Goal(predicate=("edge", "x", "y"), deadline=Decimal(0))], False)
        expected = "" \
            "(:goal (and " \
            "(cleared x y cleared-x-y-0 ) " \
            "))\n"

        # when
        encode_goal(self.out, goals)
        actual = self.out.getvalue()

        # then
        self.assertEqual(expected, actual)

    def test_encode_metric_generic(self):
        # given
        goals = convert_goals([
            Goal(predicate=("rescued", "civ1"), deadline=Decimal(0)),
            Goal(predicate=("rescued", "civ2"), deadline=Decimal(0))
        ], False)

        metric = {
            "type": "minimize",
            "weights": {"total-time": 1, "soft-goal-violations": {"rescued": 1000}}
        }
        expected = "" \
            "(:metric minimize (+ " \
            "(* 1 (total-time )  ) " \
            "(* 1000 (is-violated pref-rescued-civ1-0 )  ) " \
            "(* 1000 (is-violated pref-rescued-civ2-0 )  ) " \
            ") ) \n"

        # when
        encode_metric(self.out, metric, goals)
        actual = self.out.getvalue()

        self.assertEqual(expected, actual)

    def test_encode_metric_specific(self):
        # given
        goals = convert_goals([Goal(predicate=("rescued", "civ1"), deadline=Decimal(0))], False)
        metric = {
            "type": "minimize",
            "weights": {"soft-goal-violations": {goals[0].goal: 1000}}
        }
        expected = "" \
            "(:metric minimize (+ " \
            "(* 1000 (is-violated pref-rescued-civ1-0 )  ) " \
            ") ) \n"

        # when
        encode_metric(self.out, metric, goals)
        actual = self.out.getvalue()

        self.assertEqual(expected, actual)

    def test_encode_metric_edge(self):
        # given
        goals = convert_goals([Goal(predicate=("edge", "x", "y"), deadline=Decimal(0))], False)
        metric = {
            "type": "minimize",
            "weights": {"soft-goal-violations": {"edge": 1000}}
        }
        expected = "" \
            "(:metric minimize (+ " \
            "(* 1000 (is-violated pref-cleared-x-y-0 )  ) " \
            ") ) \n"

        # when
        encode_metric(self.out, metric, goals)
        actual = self.out.getvalue()

        self.assertEqual(expected, actual)


class TestCreatePredicate(TestCase):

    def test_create_list_predicate(self):
        # given
        predicate_name = "name"
        value = "v1", "v2"
        object_name = None

        # when
        actual = create_predicate(predicate_name, value, object_name)

        # then
        self.assertEqual((predicate_name,) + value, actual)

    def test_create_true_predicate(self):
        predicate_name = "name"
        value = True
        object_name = "object"

        # when
        actual = create_predicate(predicate_name, value, object_name)

        # then
        self.assertEqual((predicate_name, object_name), actual)

    def test_create_function_predicate(self):
        predicate_name = "name"
        value = 10
        object_name = "object"

        # when
        actual = create_predicate(predicate_name, value, object_name)

        # then
        self.assertEqual(("=", (predicate_name, object_name), value), actual)

    def test_create_function_list_predicate(self):
        predicate_name = "name"
        value = [True, 10]
        object_name = "object"

        # when
        actual = create_predicate(predicate_name, value, object_name)

        # then
        self.assertEqual(("=", (predicate_name, object_name), 10), actual)


class TestDeadlineEncoding(TestCase):

    def test_collate_object_types(self):
        # given
        objects = {"some_type": OrderedDict([("some_object_id0", "some_object"), ("some_object_id1", "some_object")])}
        goals = convert_goals([Goal(predicate=("some_predicate",), deadline=Decimal(0))], True)
        expected = {
            "some_type": ["some_object_id0", "some_object_id1"],
            "predicate": ["some_predicate-0"]
        }

        # when
        actual = collate_object_types(objects, goals)

        # then
        assert_that(actual, equal_to(expected))

    def test_collate_object_types_only_adds_for_non_rescue_goals(self):
        # given
        objects = {}
        goals = convert_goals([
            Goal(predicate=("rescued", "civ0",), deadline=Decimal(0)),
            Goal(predicate=("some_predicate",), deadline=Decimal(0)),
            Goal(predicate=("edge", "x", "y"), deadline=Decimal(0))],
            True)
        expected = {
            "predicate": ["some_predicate-0", "cleared-x-y-0"]
        }

        # when
        actual = collate_object_types(objects, goals)

        # then
        assert_that(actual, equal_to(expected))

    def test_encode_objects_with_predicates(self):
        # given
        objects = {"predicate": ["some_predicate-150"]}
        expected = "(:objects some_predicate-150 - predicate )\n"
        out = StringIO()

        # when
        encode_objects(out, objects)
        actual = out.getvalue()

        # then
        assert_that(actual, equal_to(expected))

    def test_encode_goals_with_finite_deadlines(self):
        # given
        goals = convert_goals([Goal(predicate=("predicate",), deadline=Decimal(0))], True)
        out = StringIO()
        expected = "(required predicate-0 ) (at 0 (not (required predicate-0 )  )  ) "

        # when
        encode_deadlines(out, goals)
        actual = out.getvalue()

        # then
        assert_that(actual, equal_to(expected))

    def test_encode_goals_with_infinite_deadlines(self):
        # given
        goals = convert_goals([Goal(predicate=("predicate",), deadline=Decimal("inf"))], True)
        out = StringIO()
        expected = "(required predicate-Infinity ) "

        # when
        encode_deadlines(out, goals)
        actual = out.getvalue()

        # then
        assert_that(actual, equal_to(expected))

    def test_encode_goals_without_explicit_deadlines(self):
        # given
        goals = convert_goals([Goal(predicate=("rescued", "civ0"), deadline=Decimal("inf"))], True)
        out = StringIO()
        expected = ""

        # when
        encode_deadlines(out, goals)
        actual = out.getvalue()

        # then
        assert_that(actual, equal_to(expected))


class ConvertGoalsTest(TestCase):

    def test_goal_to_pddl_predicate_finite(self):
        # given
        goal = Goal(predicate=("predicate",), deadline=Decimal(0))

        # when
        actual, = convert_goals([goal], True)

        # then
        assert_that(actual.predicate_name, equal_to("predicate-0"))

    def test_goal_to_pddl_predicate_infinite(self):
        # given
        goal = Goal(predicate=("predicate",), deadline=Decimal("inf"))

        # when
        actual, = convert_goals([goal], True)

        # then
        assert_that(actual.predicate_name, equal_to("predicate-Infinity"))

    def test_goal_to_pddl_predicate_compound(self):
        # given
        goal = Goal(predicate=("complex", "predicate"), deadline=Decimal(0))

        # when
        actual, = convert_goals([goal], True)

        # then
        assert_that(actual.predicate_name, equal_to("complex-predicate-0"))

    def test_passes_through_use_preferences(self):
        # given
        goal = Goal(predicate=("predicate",), deadline=Decimal("inf"))

        # when
        actual_soft_goal, = convert_goals([goal], True)
        actual_hard_goal, = convert_goals([goal], False)

        # then
        assert_that(actual_soft_goal.preference, equal_to(True))
        assert_that(actual_hard_goal.preference, equal_to(False))

    def test_rescue_goal_has_no_explicit_deadline(self):
        # given
        goal = Goal(predicate=("rescued",), deadline=Decimal("inf"))

        # when
        actual, = convert_goals([goal], True)

        # then
        assert_that(actual.explicit_deadline, equal_to(False))

    def test_non_rescue_goal_has_explicit_deadline(self):
        # given
        goal = Goal(predicate=("predicate",), deadline=Decimal("inf"))

        # when
        actual, = convert_goals([goal], True)

        # then
        assert_that(actual.explicit_deadline, equal_to(True))

    def test_edge_converted_to_cleared(self):
        # given
        goal = Goal(predicate=("edge", "x", "y"), deadline=Decimal("inf"))

        # when
        actual, = convert_goals([goal], True)

        # then
        assert_that(actual.goal.predicate, equal_to(("cleared", "x", "y")))

