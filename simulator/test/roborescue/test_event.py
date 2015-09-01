__author__ = 'jack'

from unittest import TestCase

from roborescue.event import Event


class TestEvent(TestCase):

    def test_as_predicate_becomes_true(self):
        # given
        model = {
            "objects": {"civilian": {"civ1": {
                "known": {},
                "unknown": {}
            }}},
            "assumed-values": {}
        }
        event = Event(100, "civ1", "buried", becomes=True)
        expected = "at", 100, ("buried", "civ1")

        # when
        actual = event.as_predicate(0, model)

        self.assertEqual(expected, actual)

    def test_known_as_predicate_becomes_false(self):
        # given
        model = {
            "objects": {"civilian": {"civ1": {
                "known": {"alive": True},
                "unknown": {}
            }}},
            "assumed-values": {}
        }
        event = Event(100, "civ1", "alive", becomes=False)
        expected = "at", 100, ("not", ("alive", "civ1"))

        # when
        actual = event.as_predicate(0, model)

        self.assertEqual(expected, actual)

    def test_assumed_true_as_predicate_becomes_false(self):
        # given
        model = {
            "objects": {"civilian": {"civ1": {
                "known": {},
                "unknown": {"alive": {"actual": True}}
            }}},
            "assumed-values": {"alive": True}
        }
        event = Event(100, "civ1", "alive", becomes=False)
        expected = "at", 100, ("not", ("alive", "civ1"))

        # when
        actual = event.as_predicate(0, model)

        self.assertEqual(expected, actual)

    def test_assumed_false_as_predicate_becomes_false(self):
        # given
        model = {
            "objects": {"civilian": {"civ1": {
                "known": {},
                "unknown": {"alive": {"actual": True}}
            }}},
            "assumed-values": {"alive": False}
        }
        event = Event(100, "civ1", "alive", becomes=False)
        expected = None

        # when
        actual = event.as_predicate(0, model)

        self.assertEqual(expected, actual)

    def test_edge_as_predicate_becomes_true(self):
        # given
        model = {
            "graph": {
                "edges": {
                    "building1 hospital1": {"known": {}}
                }
            },
            "assumed-values": {}
        }
        event = Event(100, "building1 hospital1", "blocked", becomes=True)
        expected = "at", 100, ("blocked", "building1 hospital1")

        # when
        actual = event.as_predicate(0, model)

        self.assertEqual(expected, actual)

    def test_bidirectional_edge_as_predicate_becomes_true(self):
        # given
        model = {
            "graph": {
                "edges": {
                    "hospital1 building1": {"known": {}}
                }
            },
            "assumed-values": {}
        }
        event = Event(100, "building1 hospital1", "blocked", becomes=True)
        expected = "at", 100, ("blocked", "building1 hospital1")

        # when
        actual = event.as_predicate(0, model)

        self.assertEqual(expected, actual)
