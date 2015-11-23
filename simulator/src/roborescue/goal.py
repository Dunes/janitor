from collections import namedtuple

__author__ = 'jack'


class Goal(namedtuple("Goal", "predicate deadline")):
    pass


class Bid(namedtuple("Bid", "name value goal requirements computation_time")):
    pass
