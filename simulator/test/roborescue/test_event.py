from unittest import TestCase

from roborescue.event import ObjectEvent, EdgeEvent, Predicate, decode_event

__author__ = 'jack'


class TestEventGetPredicates(TestCase):

    def test_get_predicates_becomes_true(self):
        # given
        model = {
            "objects": {"civilian": {"civ1": {
                "known": {},
                "unknown": {}
            }}},
            "assumed-values": {}
        }
        event = ObjectEvent(100, "civ1", [Predicate("buried", True)])
        expected = [("at", 100, ("buried", "civ1"))]

        # when
        actual = event.get_predicates(0, model)

        self.assertEqual(expected, actual)

    def test_known_get_predicates_becomes_false(self):
        # given
        model = {
            "objects": {"civilian": {"civ1": {
                "known": {"alive": True},
                "unknown": {}
            }}},
            "assumed-values": {}
        }
        event = ObjectEvent(100, "civ1", [Predicate("alive", False)])
        expected = [("at", 100, ("not", ("alive", "civ1")))]

        # when
        actual = event.get_predicates(0, model)

        self.assertEqual(expected, actual)

    def test_edge_get_predicates_becomes_true(self):
        # given
        model = {
            "graph": {
                "edges": {
                    "building1 hospital1": {"known": {}}
                }
            },
            "assumed-values": {}
        }
        event = EdgeEvent(100, "building1 hospital1", [Predicate("blocked", True)])
        expected = [("at", 100, ("blocked", "building1 hospital1"))]

        # when
        actual = event.get_predicates(0, model)

        self.assertEqual(expected, actual)

    def test_multi_predicate_event(self):
        model = {
            "graph": {
                "edges": {
                    "building1 hospital1": {"known": {
                        "edge": True
                    }}
                }
            },
            "assumed-values": {}
        }

        event = EdgeEvent(100, "building1 hospital1", [
            Predicate("edge", False),
            Predicate("blocked-edge", True),
            Predicate("blockedness", 300)
        ])
        expected = [
            ("at", 100, ("not", ("edge", "building1 hospital1"))),
            ("at", 100, ("blocked-edge", "building1 hospital1")),
            ("at", 100, ("=", ("blockedness", "building1 hospital1"), 300))
        ]

        # when
        actual = event.get_predicates(0, model)

        self.assertEqual(expected, actual)


class TestEventApply(TestCase):

    def test_apply_becomes_true(self):
        # given
        actual = {}
        model = {
            "objects": {"civilian": {"civ1": {
                "known": actual,
                "unknown": {}
            }}},
            "assumed-values": {}
        }
        event = ObjectEvent(100, "civ1", [Predicate("buried", True)])

        # when
        changed = event.apply(model)

        self.assertEqual("civ1", changed)
        self.assertEqual({"buried": True}, actual)

    def test_apply_becomes_false(self):
        # given
        actual = {"alive": True}
        model = {
            "objects": {"civilian": {"civ1": {
                "known": actual,
                "unknown": {}
            }}},
            "assumed-values": {}
        }
        event = ObjectEvent(100, "civ1", [Predicate("alive", False)])

        # when
        changed = event.apply(model)

        self.assertEqual("civ1", changed)
        self.assertEqual({"alive": False}, actual)

    def test_edge_apply_becomes_true(self):
        # given
        actual = {}
        model = {
            "graph": {
                "edges": {
                    "building1 hospital1": {"known": actual}
                }
            },
            "assumed-values": {}
        }
        event = EdgeEvent(100, "building1 hospital1", [Predicate("blocked", True)])

        # when
        changed = event.apply(model)

        self.assertEqual("building1 hospital1", changed)
        self.assertEqual({"blocked": True}, actual)

    def test_multi_predicate_event(self):
        actual = {"edge": True}
        model = {
            "graph": {
                "edges": {
                    "building1 hospital1": {"known": actual}
                }
            },
            "assumed-values": {}
        }

        event = EdgeEvent(100, "building1 hospital1", [
            Predicate("edge", False),
            Predicate("blocked-edge", True),
            Predicate("blockedness", 300)
        ])

        # when
        changed = event.apply(model)

        self.assertEqual("building1 hospital1", changed)
        self.assertEqual({"edge": False, "blocked-edge": True, "blockedness": 300}, actual)


class TestDecodeEvent(TestCase):

    def test_decode_object_event(self):
        # given
        json_event = {
            "type": "object",
            "time": 60,
            "id": "some_id",
            "predicates": [
                {"name": "some_name", "becomes": True},
                {"name": "another_name", "becomes": False},
                {"name": "third_name", "becomes": 30},
            ],
            "hidden": True
        }

        # when
        event = decode_event(json_event)

        # then
        self.assertIsInstance(event, ObjectEvent)
        self.assertEqual("some_id", event.id_)
        self.assertEqual(60, event.time)
        predicates = [
            Predicate(name="some_name", becomes=True),
            Predicate(name="another_name", becomes=False),
            Predicate(name="third_name", becomes=30)
        ]
        self.assertEqual(predicates, event.predicates)
        self.assertEqual(True, event.hidden)

    def test_decode_edge_event(self):
        # given
        json_event = {
            "type": "edge",
            "time": 60,
            "id": "some_id",
            "predicates": [{"name": "some_name", "becomes": True}]
        }

        # when
        event = decode_event(json_event)

        # then
        self.assertIsInstance(event, EdgeEvent)
        self.assertEqual("some_id", event.id_)
        self.assertEqual(60, event.time)
        self.assertEqual([Predicate(name="some_name", becomes=True)], event.predicates)
        self.assertEqual(False, event.hidden)
