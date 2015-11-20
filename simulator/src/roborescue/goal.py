from collections import namedtuple
from functools import total_ordering

__author__ = 'jack'


@total_ordering
class Goal(namedtuple("Goal", "predicate deadline")):
    def __lt__(self, other):
        if not isinstance(other, Goal):
            return NotImplemented
        return self.deadline < other.deadline
