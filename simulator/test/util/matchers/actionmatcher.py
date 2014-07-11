import hamcrest

from unittest.mock import sentinel

import action

__all__ = ["equal_to"]

def equal_to(action_):
    if type(action_) in matchers:
        return IsSameAction(action_)
    else:
        return hamcrest.equal_to(action_)

class IsSameAction(hamcrest.base_matcher.BaseMatcher):

    def __init__(self, expected_action):
        self.expected_action = expected_action
        self.matcher = matchers[type(expected_action)]

    def _matches(self, actual_action):
        return self.matcher(self.expected_action, actual_action)

    def describe_to(self, description):
        description.append("<")
        description.append(str(self.expected_action))
        description.append(">")

def same_partial(expected, actual):
    return (getattr(expected, "partial", sentinel.partial) ==
            getattr(actual, "partial", sentinel.partial))


def match_move(expected, actual):
    return (same_partial(expected, actual)
        and expected.agent == actual.agent
        and expected.start_time == actual.start_time
        and expected.duration == actual.duration
        and expected.start_node == actual.start_node
        and expected.end_node == actual.end_node)

def match_action(expected, actual):
    return (same_partial(expected, actual)
        and expected.start_time == actual.start_time
        and expected.duration == actual.duration)

def match_clean(expected, actual):
    return (same_partial(expected, actual)
        and expected.agent == actual.agent
        and expected.start_time == actual.start_time
        and expected.duration == actual.duration
        and expected.room == actual.room)

def match_extra_clean(expected, actual):
    return (same_partial(expected, actual)
        and expected.agent0 == actual.agent0
        and expected.agent1 == actual.agent1
        and expected.start_time == actual.start_time
        and expected.duration == actual.duration
        and expected.room == actual.room)

def match_observe(expected, actual):
    return (same_partial(expected, actual)
        and expected.agent == actual.agent
        and expected.node == actual.node
        and expected.start_time == actual.start_time
        and expected.duration == actual.duration)

def match_plan(expected, actual):
    return (same_partial(expected, actual)
        and expected.agent == actual.agent
        and expected.start_time == actual.start_time
        and expected.duration == actual.duration)

def match_stalled(expected, actual):
    return (same_partial(expected, actual)
        and expected.agent == actual.agent
        and expected.start_time == actual.start_time
        and expected.duration == actual.duration)

matchers = {
    action.Action: match_action,
    action.Move: match_move,
    action.Clean: match_clean,
    action.ExtraClean: match_extra_clean,
    action.Observe: match_observe,
    action.Plan: match_plan,
    action.Stalled: match_stalled
}


