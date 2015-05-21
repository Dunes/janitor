__author__ = 'jack'

import unittest

import hamcrest
from hamcrest import assert_that, contains, is_not, empty, is_, has_length, has_item, equal_to, any_of

from action import Action, Clean
from planner import Planner


class ActionMatcher(hamcrest.base_matcher.BaseMatcher):
    def __init__(self, attr, value, cls=Action):
        self.attr = attr
        self.value = value
        self.cls = cls

    def _matches(self, other):
        return isinstance(other, self.cls) and getattr(other, self.attr) == self.value

    def describe_to(self, description):
        description.append("{} with {} == {!r}".format(self.cls.__name__, self.attr, self.value))


def with_agent(agent):
    return ActionMatcher("agent", agent)


def with_room(room):
    return ActionMatcher("room", room, Clean)


class TestGetPlan(unittest.TestCase):

    def setUp(self):
        self.planner = Planner(10,
                               planner_location="../../optic-cplex",
                               domain_file="../../janitor/janitor-domain.pddl")
        self.model = {
            "assumed-values": {},
            "domain": "janitor",
            "problem": "test-problem",
            "agents": {
                "agent1": {
                    "agent": True,
                    "available": True,
                    "at": [True, "empty-rm1"]
                },
                "agent2": {
                    "agent": True,
                    "available": True,
                    "at": [True, "empty-rm1"]
                }
            },
            "nodes": {
                "empty-rm1": {"node": True},
                "rm1": {
                    "is-room": True,
                    "node": True,
                    "cleaned": False,
                    "dirty": True,
                    "dirtiness": 20,
                    "extra-dirty": False
                },
                "rm2": {
                    "is-room": True,
                    "node": True,
                    "cleaned": False,
                    "dirty": True,
                    "dirtiness": 20,
                    "extra-dirty": False
                }
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
        assert_that(result , is_(None))

    def test_one_goal(self):
        goal = [["cleaned", "rm1"]]
        result = self.planner.get_plan(self.model, goals=goal)

        assert_that(result, has_item(any_of(with_agent("agent1"), with_agent("agent2"))))
        assert_that(result, has_item(with_room("rm1")))
        assert_that(result, is_not(has_item(with_room("rm2"))))

    def test_mini(self):
        import pddl_parser
        from io import StringIO
        out = StringIO()
        pddl_parser.encode_problem(out, self.model, "all", None)

        assert_that(out.getvalue(), is_(None))