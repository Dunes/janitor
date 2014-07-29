import logging

from functools import total_ordering
from enum import Enum
from accuracy import increment
from planning_exceptions import ExecutionError

from logger import StyleAdapter

log = StyleAdapter(logging.getLogger(__name__))


class OrderedEnum(Enum):
    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


class ExecutionState(OrderedEnum):
    pre_start = 2
    executing = 1
    finished = 0


@total_ordering
class ActionState(object):

    def __init__(self, action, time=None, state=ExecutionState.pre_start):
        object.__setattr__(self, "time", action.start_time if time is None else time)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "action", action)

    def start(self):
        if self.state != ExecutionState.pre_start:
            raise ExecutionError("invalid state")
        object.__setattr__(self, "state", ExecutionState.executing)
        object.__setattr__(self, "time", self.action.end_time - increment)

    def finish(self):
        log.info("finishing: {}", self.action)
        if self.state != ExecutionState.executing:
            raise ExecutionError("invalid state")
        object.__setattr__(self, "state", ExecutionState.finished)

    def __iter__(self):
        yield self.time
        yield self.state
        yield self.action

    def __lt__(self, other):
        return tuple(self) < tuple(other)

    def __eq__(self, other):
        return tuple(self) == tuple(other)

    def __setattr__(self, key, value):
        raise TypeError("ActionStates should not be directly manipulated")

    def __delattr__(self, item):
        raise TypeError("ActionStates should not be directly manipulated")

    def __str__(self):
        return "ActionState(time={arg.time!s}, state={arg.state!s}, action={arg.action!s})".format(arg=self)

    __repr__ = __str__