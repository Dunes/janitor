"""
Created on 20 Jun 2014

@author: jack
"""
__author__ = 'jack'

import hamcrest
from hamcrest import anything, equal_to
from hamcrest.core.core.isanything import IsAnything


from roborescue.problem_encoder import find_object

__all__ = ["has_agent", "has_edge", "has_node"]


class HasObject(hamcrest.base_matcher.BaseMatcher):

    def with_object(self, object_id):
        self.object_id = object_id
        return self

    def _matches(self, objects):
        try:
            find_object(self.object_id, objects)
        except KeyError:
            return False
        else:
            return True

    def describe_to(self, description):
        description.append("model with object {!r}".format(self.object_id))


class HasAgent(HasObject):

    def at(self, at):
        self.at = at
        return self

    def _matches(self, model):
        agent_state = find_object(self.object_id, model["objects"])
        if "at" in agent_state and len(agent_state["at"]) == 2:
            return agent_state["at"][1] == self.at
        return False

    def describe_to(self, description):
        description.append("model with agent {!r} at {!r}".format(self.object_id, self.at))


class HasEdge(hamcrest.base_matcher.BaseMatcher):

    distance = anything()
    from_node = anything()
    to_node = anything()

    def with_distance(self, distance):
        self.distance = distance
        return self

    def from_(self, from_node):
        self.from_node = from_node
        return self

    def to(self, to_node):
        self.to_node = to_node
        return self

    def _matches(self, edges):
        if isinstance(self.from_node, IsAnything) and isinstance(self.to_node, IsAnything):
            edge_id = self.from_node
        else:
            edge_id = " ".join((self.from_node, self.to_node))
        try:
            edge = edges[edge_id]
        except KeyError:
            return False
        return edge["known"]["distance"] == self.distance

    def describe_to(self, description):
        description.append("graph with edge {!r} and distance {}".format(" ".join((self.from_node, self.to_node)),
            self.distance))


class HasNode(hamcrest.base_matcher.BaseMatcher):

    def with_node(self, node):
        self.node = node
        return self

    def with_value(self, not_room=None, **kwargs):
        if not not_room:
            if "known" in kwargs:
                kwargs["known"]["is-room"] = True
            else:
                kwargs["is-room"] = True
        self.node_value = kwargs
        return self

    def _matches(self, model):
        self.has_node = self.node in model["nodes"]
        self.has_value = self.has_node \
            and equal_to(self.node_value).matches(model["nodes"][self.node])
        return self.has_node and self.has_value

    def describe_to(self, description):
        if not self.has_node:
            description.append("node with name {!r}".format(self.node))
        if not self.has_value:
            if not self.has_node:
                description.append(" and having value {!r}".format(self.node_value))
            else:
                description.append("node having value {!r}".format(self.node_value))


def has_node(node):
    return HasNode().with_node(node)


def has_object(object_id):
    return HasObject().with_object(object_id)


def has_agent(agent):
    return HasAgent().with_object(agent)


def has_edge():
    return HasEdge()
