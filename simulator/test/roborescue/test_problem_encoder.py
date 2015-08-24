__author__ = 'jack'

from unittest import TestCase
from io import StringIO
from collections import OrderedDict

from roborescue.problem_encoder import (_encode_objects, _encode_init, _encode_graph, _collate_objects, _encode_goal,
     _encode_metric, create_predicate)


class ProblemEncoderTest(TestCase):

    def setUp(self):
        self.out = StringIO()
        """
        {
            'domain': 'roborescue',
            'events': [{
                'becomes': False,
                'object': 'civ1',
                'predicate': 'alive',
                'time': 200
            }],
            'goal': {'soft-goals': [['rescued', 'civ1'], ['rescued', 'civ2']]},
            'graph': {
                'bidirectional': True,
                'edges': {
                    'building1 hospital1': {
                        'known': {'distance': 50},
                        'unknown': {'blocked-edge': {'actual': True}, 'blockedness': {'actual': 10, 'max': 100, 'min': 0}}
                    }
                }
            },
            'metric': {'type': 'minimize',
            'weights': {'soft-goal-violations': {'rescued': 1000}, 'total-time': 1}},
            'objects': "",
            'problem': 'roborescue-problem-test'
        }
        """

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
        _encode_objects(self.out, objects)
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
        _encode_init(self.out, objects, {"edges": {}, "bidirectional": False}, assumed_values)
        actual = self.out.getvalue()

        # then
        expected = "(:init " \
                   "(alive civ1 ) " \
                   "(at civ1 building1 ) " \
                   "(buried civ1 ) " \
                   "(= (buriedness civ1 ) 100) " \
                   "(at police1 hospital1 ) ) "
        self.assertEqual(expected, actual)

    def test_encode_graph_with_unknown_edge(self):
        # given
        graph = {
            "edges": {
                "building1 hospital1": OrderedDict([
                    ("known", OrderedDict([
                        ("distance", 50),
                        ("edge", True),
                    ])),
                    ("unknown", OrderedDict([
                        ("blockedness", {"max": 100, "min": 0, "actual": 10})
                    ]))
                ])
            },
            "bidirectional": True
        }
        assumed_values = {"blocked-edge": False, "blockedness": "max"}

        # when
        _encode_graph(self.out, graph, assumed_values)
        actual = self.out.getvalue()

        # then
        expected = "(= (distance building1 hospital1 ) 50) " \
            + "(edge building1 hospital1 ) " \
            + "(= (blockedness building1 hospital1 ) 100) " \
            + "(= (distance hospital1 building1 ) 50) " \
            + "(edge hospital1 building1 ) " \
            + "(= (blockedness hospital1 building1 ) 100) "
        self.assertEqual(expected, actual)

    def test_encode_graph_with_known_edge(self):
        # given
        graph = {
            "edges": {
                "building1 hospital1": OrderedDict([
                    ("known", OrderedDict([
                        ("distance", 50),
                        ("edge", True),
                    ])),
                    ("unknown", OrderedDict([
                        ("blockedness", {"max": 100, "min": 0, "actual": 10})
                    ]))
                ])
            },
            "bidirectional": True
        }
        assumed_values = {"blocked-edge": False, "blockedness": "max"}

        # when
        _encode_graph(self.out, graph, assumed_values)
        actual = self.out.getvalue()

        # then
        expected = "(= (distance building1 hospital1 ) 50) " \
            + "(edge building1 hospital1 ) " \
            + "(= (blockedness building1 hospital1 ) 100) " \
            + "(= (distance hospital1 building1 ) 50) " \
            + "(edge hospital1 building1 ) " \
            + "(= (blockedness hospital1 building1 ) 100) "
        self.assertEqual(expected, actual)

    def test_encode_graph_with_known_blocked_edge(self):
        # given
        graph = {
            "edges": {
                "building1 hospital1": OrderedDict([
                    ("known", OrderedDict([
                        ("distance", 50),
                        ("blocked-edge", True),
                    ])),
                    ("unknown", OrderedDict([
                        ("blockedness", {"max": 100, "min": 0, "actual": 10})
                    ]))
                ])
            },
            "bidirectional": True
        }
        assumed_values = {"blocked-edge": False, "blockedness": "max"}

        # when
        _encode_graph(self.out, graph, assumed_values)
        actual = self.out.getvalue()

        # then
        expected = "(= (distance building1 hospital1 ) 50) " \
            + "(blocked-edge building1 hospital1 ) " \
            + "(= (blockedness building1 hospital1 ) 100) " \
            + "(= (distance hospital1 building1 ) 50) " \
            + "(blocked-edge hospital1 building1 ) " \
            + "(= (blockedness hospital1 building1 ) 100) "
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
        actual = _collate_objects(objects)

        # then
        self.assertEqual(expected, actual)

    def test_encode_soft_goal(self):
        # given
        goals = {"soft-goals": [["rescued", "civ1"], ["rescued", "civ2"]]}
        expected = "" \
            "(:goal (and " \
            "(preference rescued-civ1 (rescued civ1 )  ) " \
            "(preference rescued-civ2 (rescued civ2 )  ) " \
            "))\n"

        # when
        _encode_goal(self.out, goals)
        actual = self.out.getvalue()

        # then
        self.assertEqual(expected, actual)

    def test_encode_metric(self):
        # given
        goals = {"soft-goals": [["rescued", "civ1"], ["rescued", "civ2"]]}
        metric = {
            "type": "minimize",
            "weights": {"total-time": 1, "soft-goal-violations": {"rescued": 1000}}
        }
        expected = "" \
            "(:metric minimize (+ " \
            "(* 1 (total-time )  ) " \
            "(* 1000 (is-violated rescued-civ1 )  ) " \
            "(* 1000 (is-violated rescued-civ2 )  ) " \
            ") ) \n"

        # when
        _encode_metric(self.out, metric, goals)
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

    def test_create_false_predicate(self):
        predicate_name = "name"
        value = False
        object_name = "object"

        # when
        actual = create_predicate(predicate_name, value, object_name, include_not=True)

        # then
        self.assertEqual(("not", (predicate_name, object_name)), actual)

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