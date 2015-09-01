__author__ = 'jack'

from action import *
from .problem_encoder import find_object
from planning_exceptions import ExecutionError

from logger import StyleAdapter
from logging import getLogger

log = StyleAdapter(getLogger(__name__))


class Move(Action):

    _format_attrs = ("start_time", "duration", "agent", "start_node", "end_node", "partial")

    def __init__(self, start_time, duration, agent, start_node, end_node, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "start_node", start_node)
        object.__setattr__(self, "end_node", end_node)

    def is_applicable(self, model):
        return find_object(self.agent, model["objects"])["at"][1] == self.start_node \
            and model["graph"]["edges"][self.start_node + " " + self.end_node]["known"].get("edge")

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        find_object(self.agent, model["objects"])["at"][1] = self.end_node
        if self.start_node.startswith("temp"):
            del model["objects"]["node"][self.start_node]
            del model["graph"]["edges"][self.start_node + " " + self.end_node]
        return False

    def partially_apply(self, model, deadline):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        # create temp node
        continued_partial_move = self.start_node.startswith("temp")
        if continued_partial_move:
            self.modify_temp_node(model, deadline)
        else:
            self.create_temp_node(model, deadline)
        return False

    def modify_temp_node(self, model, deadline):
        temp_node_name = self.start_node

        edges = model["graph"]["edges"]

        back_edge_id, forward_edge_id = (edge_id for edge_id in edges if edge_id.startswith(temp_node_name))

        if forward_edge_id.endswith(self.end_node):
            distance_moved = deadline - self.start_time
        elif back_edge_id.endswith(self.end_node):
            distance_moved = self.start_time - deadline
        else:
            raise ExecutionError("Neither temp node edge links to end_node: edges: {}, action: {}"
                .format([back_edge_id, forward_edge_id], self))

        edges[back_edge_id]["known"]["distance"] += distance_moved
        edges[forward_edge_id]["known"]["distance"] -= distance_moved

        assert edges[back_edge_id]["known"]["distance"] > 0
        assert edges[forward_edge_id]["known"]["distance"] > 0

        # create partial action representing move
        action = Move(self.start_time, distance_moved, self.agent, temp_node_name, self.end_node, partial=True)
        return action

    def create_temp_node(self, model, deadline):
        temp_node_name = "-".join(("temp", self.agent, self.start_node, self.end_node))
        if temp_node_name in model["objects"]["node"] or \
                temp_node_name in model["graph"]["edges"]:
            log.error("tried to insert {}, but already initialised", temp_node_name)
            assert False
        model["objects"]["node"][temp_node_name] = {}
        # set up edges -- only allow movement out of node
        distance_moved = deadline - self.start_time
        distance_remaining = self.get_edge_length(model, self.start_node, self.end_node) - distance_moved
        model["graph"]["edges"].update(self._create_temp_edge_pair(temp_node_name, self.start_node, self.end_node,
            distance_moved, distance_remaining))
        # move agent to temp node
        find_object(self.agent, model["objects"])["at"][1] = temp_node_name
        # create partial action representing move
        action = Move(self.start_time, distance_moved, self.agent, self.start_node, temp_node_name, partial=True)
        return action

    @staticmethod
    def _create_temp_edge_pair(temp_node, start_node, end_node, moved, remaining):
        return (
            (" ".join((temp_node, end_node)), {
                "known": {
                    "distance": remaining,
                    "edge": True,
                },
                "unknown": {}
            }),
            (" ".join((temp_node, start_node)), {
                "known": {
                    "distance": moved,
                    "edge": True,
                },
                "unknown": {}
            }),
        )

    def get_edge_length(self, model, start_node, end_node):
        edge_key = " ".join((start_node, end_node))
        try:
            edge = model["graph"]["edges"][edge_key]
        except KeyError:
            pass
        else:
            return edge["known"]["distance"]
        if model["graph"]["bidirectional"]:
            raise NotImplementedError
        raise ExecutionError("Could not find {!r}".format(edge_key))


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
