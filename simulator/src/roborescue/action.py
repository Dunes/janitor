__author__ = 'jack'

from action import *


class Move(Action):

    _format_attrs = ("start_time", "duration", "agent", "start_node", "end_node", "partial")

    def __init__(self, start_time, duration, agent, start_node, end_node, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "start_node", start_node)
        object.__setattr__(self, "end_node", end_node)


class Unblock(Action):

    _format_attrs = ("start_time", "duration", "agent", "start_node", "end_node", "partial")

    def __init__(self, start_time, duration, agent, start_node, end_node, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "start_node", start_node)
        object.__setattr__(self, "end_node", end_node)


class Load(Action):

    _format_attrs = ("start_time", "duration", "agent", "target", "node", "partial")

    def __init__(self, start_time, duration, agent, target, node, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "node", node)


class Unload(Action):

    _format_attrs = ("start_time", "duration", "agent", "target", "node", "partial")

    def __init__(self, start_time, duration, agent, target, node, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "node", node)


class Rescue(Action):

    _format_attrs = ("start_time", "duration", "agent", "target", "node", "partial")

    def __init__(self, start_time, duration, agent, target, node, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "node", node)
