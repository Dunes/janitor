import logging

from functools import total_ordering
from collections import namedtuple
from planning_exceptions import ExecutionError

from logger import StyleAdapter

log = StyleAdapter(logging.getLogger(__name__))

@total_ordering
class ExecutionState(object):
    def __init__(self, desc, ordinal):
        self.desc = desc
        self.ordinal = ordinal
    def __lt__(self, other):
        return self.ordinal < other.ordinal
    def __str__(self):
        return self.desc
    __repr__ = __str__

ExecutionState = namedtuple("_ExecutionState", "pre_start executing finished")(
    *(ExecutionState(desc,-ordinal) for ordinal, desc in enumerate(("pre_start", "executing", "finished")))
)

@total_ordering
class ActionState(object):

    def __init__(self, action, time=None, state=ExecutionState.pre_start):
        self.time = action.start_time if time is None else time
        self.state = state
        self.action = action

    def start(self):
        if self.state != ExecutionState.pre_start:
            raise ExecutionError("invalid state")
        self.state = ExecutionState.executing
        self.time = self.action.end_time

    def finish(self):
        log.info("finishing: {}", self.action)
        if self.state != ExecutionState.executing:
            raise ExecutionError("invalid state")
        self.state = ExecutionState.finished

    def __iter__(self):
        return iter((self.time, self.state, self.action))

    def __lt__(self, other):
        if self.time != other.time:
            return self.time < other.time
        if self.state != other.state:
            return self.state < other.state
        return self.action < other.action

    def __eq__(self, other):
        return self.time == other.time and self.state == other.state and self.action == other.action