__author__ = 'jack'

import unittest
from io import StringIO
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event, Lock

import hamcrest
from hamcrest import assert_that, is_not, has_item, equal_to, any_of

from accuracy import as_next_end_time
from janitor.action import Action, Clean
from janitor import plan_decoder
from planner import Planner, NoPlanException, synchronized
from pddl_parser import CleaningWindowTil
from problem_encoder import _encode_predicate


class ActionMatcher(hamcrest.base_matcher.BaseMatcher):

    sentinel = object()

    def __init__(self, attrs, values, cls=Action):
        self.attrs = attrs
        self.values = values
        self.cls = cls

    def _matches(self, other):
        return isinstance(other, self.cls) and \
            all(getattr(other, attr, self.sentinel) == value for attr, value in zip(self.attrs, self.values))

    def describe_to(self, description):
        description.append("{} with {} == {!r}".format(self.cls.__name__, self.attrs, self.values))


def with_agent(agent, **kwargs):
    return ActionMatcher(["agent"] + list(kwargs), [agent] + list(kwargs.values()))



def with_room(room):
    return ActionMatcher(["room"], [room], Clean)


room_spec = {
    "is-room": True,
    "node": True,
    "cleaned": False,
    "dirty": True,
    "dirtiness": 20,
    "extra-dirty": False
}
agent_spec = {"agent": True, "available": True, "at": [True, "empty-rm1"]}


class TestGetPlan(unittest.TestCase):

    def setUp(self):
        self.planner = Planner(planning_time=10,
                               decoder=plan_decoder,
                               planner_location="../../optic-cplex",
                               domain_file="../../janitor/janitor-domain.pddl")

        self.model = {
            "assumed-values": {},
            "domain": "janitor",
            "problem": "test-problem",
            "agents": {
                "agent1": dict(agent_spec),
                "agent2": dict(agent_spec)
            },
            "nodes": {
                "empty-rm1": {"node": True},
                "rm1": dict(room_spec),
                "rm2": dict(room_spec)
            },
            "graph": {
                "edges": [
                    ["empty-rm1", "rm1", 20],
                    ["empty-rm1", "rm2", 20]
                ],
                "bidirectional": True
            },
            "goal": {
                "hard-goals": [
                    ["cleaned", "rm1"],
                    ["cleaned", "rm2"]
                ]
            },
            "metric": {
                "type": "minimize",
                "predicate": ["total-time"]
            }
        }

    def test_all_does_all_goals(self):
        result = self.planner.get_plan(self.model)
        assert_that(result, has_item(with_agent("agent1")))
        assert_that(result, has_item(with_agent("agent2")))
        assert_that(result, has_item(with_room("rm1")))
        assert_that(result, has_item(with_room("rm2")))

    def test_one_agent(self):
        result = self.planner.get_plan(self.model, agent="agent1")

        assert_that(result, has_item(with_agent("agent1")))
        assert_that(result, is_not(has_item(with_agent("agent2"))))
        assert_that(result, has_item(with_room("rm1")))
        assert_that(result, has_item(with_room("rm2")))

    def test_one_goal(self):
        goal = [["cleaned", "rm1"]]
        result = self.planner.get_plan(self.model, goals=goal)

        assert_that(result, has_item(any_of(with_agent("agent1"), with_agent("agent2"))))
        assert_that(result, has_item(with_room("rm1")))
        assert_that(result, is_not(has_item(with_room("rm2"))))


class TestCleaningWindowTil(unittest.TestCase):

    def test_add_predicate(self):
        # given
        time = 10
        room = "rm1"
        til = CleaningWindowTil(time, room, True)

        # when
        predicate = til.as_predicate()

        # then
        assert_that(predicate, equal_to(["at", time, ["cleaning-window", room]]))

    def test_remove_predicate(self):
        # given
        time = Decimal(10)
        room = "rm1"
        til = CleaningWindowTil(time, room, False)

        # when
        predicate = til.as_predicate()

        # then
        assert_that(predicate, equal_to(["at", as_next_end_time(time), ["not", ["cleaning-window", room]]]))

    def test_encode_til_predicate(self):
        # given
        time = 10
        room = "rm1"
        til = CleaningWindowTil(time, room, True)
        out = StringIO()

        # when
        predicate = til.as_predicate()
        _encode_predicate(out, predicate)
        string = out.getvalue()

        # then
        assert_that(string, equal_to("(at 10 (cleaning-window rm1 )  ) "))

    def test_encode_til_predicate_with_decimal_time(self):
        # given
        time = Decimal(10)
        room = "rm1"
        til = CleaningWindowTil(time, room, True)
        out = StringIO()

        # when
        predicate = til.as_predicate()
        _encode_predicate(out, predicate)
        string = out.getvalue()

        # then
        assert_that(string, equal_to("(at 10 (cleaning-window rm1 )  ) "))


class TestSingleAgentGetPlan(unittest.TestCase):

    def setUp(self):
        self.planner = Planner(planning_time=10,
                               decoder=plan_decoder,
                               planner_location="../../optic-cplex",
                               domain_file="../../janitor/janitor-single-domain.pddl")
        self.model = {
            "assumed-values": {},
            "domain": "janitor",
            "problem": "test-problem",
            "agents": {
                "agent1": dict(agent_spec),
            },
            "nodes": {
                "empty-rm1": {"node": True},
                "ed-rm1": dict(room_spec, **{"dirty": False, "extra-dirty": True}),
            },
            "graph": {
                "edges": [
                    ["empty-rm1", "ed-rm1", 20],
                ],
                "bidirectional": True
            },
            "goal": {
                "hard-goals": [
                    ["cleaned", "ed-rm1"],
                ]
            },
            "metric": {
                "type": "minimize",
                "predicate": ["total-time"]
            }
        }

    def test_turn_til_on(self):
        # given
        til = CleaningWindowTil(1, "ed-rm1", True)

        # when
        plan = self.planner.get_plan(self.model, tils=[til])

        # then
        assert_that(plan, has_item(with_agent("agent1", room="ed-rm1")))

    def test_turn_til_off(self):
        # given
        til0 = CleaningWindowTil(1, "ed-rm1", True)
        til1 = CleaningWindowTil(Decimal(21), "ed-rm1", False)

        # then
        with self.assertRaises(NoPlanException):
            self.planner.get_plan(self.model, tils=[til0, til1])

    def test_delayed_til_means_delayed_action(self):
        # given
        til = CleaningWindowTil(30, "ed-rm1", True)

        # when
        plan = self.planner.get_plan(self.model, tils=[til])

        # then
        assert_that(plan, has_item(with_agent("agent1", room="ed-rm1", start_time=30)))


class TestTilEffectsActionOrder(unittest.TestCase):

    def setUp(self):
        self.planner = Planner(planning_time=10,
                               decoder=plan_decoder,
                               planner_location="../../optic-cplex",
                               domain_file="../../janitor/janitor-single-domain.pddl")
        self.model = {
            "assumed-values": {},
            "domain": "janitor",
            "problem": "test-problem",
            "agents": {
                "agent1": dict(agent_spec),
            },
            "nodes": {
                "empty-rm1": {"node": True},
                "ed-rm1": dict(room_spec, **{"dirty": False, "extra-dirty": True}),
                "rm1": dict(room_spec),
            },
            "graph": {
                "edges": [
                    ["empty-rm1", "ed-rm1", 20],
                    ["empty-rm1", "rm1", 20]
                ],
                "bidirectional": True
            },
            "goal": {
                "hard-goals": [
                    ["cleaned", "ed-rm1"],
                    ["cleaned", "rm1"],
                ]
            },
            "metric": {
                "type": "minimize",
                "predicate": ["total-time"]
            }
        }

    def test_early_window_means_edrm1_cleaned_first(self):
        # given
        til_start = CleaningWindowTil(20, "ed-rm1", True)
        til_end = CleaningWindowTil(Decimal(41), "ed-rm1", False)

        # when
        plan = self.planner.get_plan(self.model, tils=[til_start, til_end])

        # then
        assert_that(plan, has_item(with_agent("agent1", room="ed-rm1", start_time=20, duration=20)))
        assert_that(plan, has_item(with_agent("agent1", room="rm1", start_time=80, duration=20)))

    def test_late_window_means_edrm1_cleaned_last(self):
        # given
        til_start = CleaningWindowTil(41, "ed-rm1", True)

        # when
        plan = self.planner.get_plan(self.model, tils=[til_start])

        # then
        assert_that(plan, has_item(with_agent("agent1", room="rm1", start_time=20, duration=20)))
        assert_that(plan, has_item(with_agent("agent1", room="ed-rm1", start_time=80, duration=20)))

class TestSynchronisedWontLetTwoFunctionsRunAtSameTime(unittest.TestCase):

    def setUp(self):

        lock = Lock()

        self.event1 = Event()
        self.event2 = Event()

        @synchronized(lock)
        def f1():
            self.event1.wait()
        self.f1 = f1

        @synchronized(lock)
        def f2():
            self.event2.wait()
        self.f2 = f2

    def test_set_events_in_order_then_functions_complete_in_order_submitted(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.f1), executor.submit(self.f2)]

            self.event1.set()
            self.event2.set()

            completed = list(as_completed(futures))

            assert_that(completed, equal_to(futures))

    def test_set_events_in_reverse_order_then_functions_complete_in_order_submitted(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.f1), executor.submit(self.f2)]

            self.event2.set()
            self.event1.set()

            completed = list(as_completed(futures))

            assert_that(completed, equal_to(futures))
