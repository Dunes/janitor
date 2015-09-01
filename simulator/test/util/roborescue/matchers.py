"""
Created on 20 Jun 2014

@author: jack
"""
__author__ = 'jack'

import hamcrest
from hamcrest import anything, is_, is_not
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

    _at = anything()
    _available = anything()
    _empty = anything()
    _carrying = anything()
    _failed_matcher = None
    _failed_name = None

    def at(self, at):
        self._at = is_(at)
        return self

    def available(self, available):
        self._available = is_(available)
        return self

    def empty(self, empty):
        self._empty = is_(empty)
        return self

    def carrying(self, carrying):
        self._carrying = is_(carrying)
        return self

    def _matches(self, objects):
        agent_state = find_object(self.object_id, objects)
        if not self._available.matches(agent_state.get("available")):
            self._failed_matcher = self._available
            self._failed_name = "available"
            return False
        if not self._empty.matches(agent_state.get("empty")):
            self._failed_matcher = self._empty
            self._failed_name = "empty"
            return False
        if not self._carrying.matches(agent_state.get("carrying", (None, None))[1]):
            self._failed_matcher = self._carrying
            self._failed_name = "carrying"
            return False
        if "at" in agent_state and len(agent_state["at"]) == 2:
            if self._at.matches(agent_state["at"][1]):
                return True
        self._failed_matcher = self._at
        self._failed_name = "at"
        return False

    def describe_to(self, description):
        description.append_text("model with agent {!r} with {!r} equal to: ".format(self.object_id, self._failed_name))
        description.append_description_of(self._failed_matcher)


class HasEdge(hamcrest.base_matcher.BaseMatcher):

    distance = anything()
    from_node = anything()
    to_node = anything()
    blockedness = anything()
    edge_type = "edge"

    def with_distance(self, distance):
        self.distance = is_(distance)
        return self

    def from_(self, from_node):
        self.from_node = from_node
        return self

    def to(self, to_node):
        self.to_node = to_node
        return self

    def unblocked(self):
        self.blockedness = 0
        self.edge_type = "edge"
        return self

    def blocked(self, blockedness):
        self.blockedness = blockedness
        self.edge_type = "blocked-edge" if blockedness else "edge"
        return self

    def _matches(self, edges):
        if isinstance(self.from_node, IsAnything) and isinstance(self.to_node, IsAnything):
            edge_id = self.from_node
        else:
            edge_id = " ".join((self.from_node, self.to_node))
        edge = edges.get(edge_id)
        if edge is None:
            return False
        if not edge["known"].get(self.edge_type, False):
            return False
        if is_not(self.blockedness).matches(edge["known"].get("blockedness", 0)):
            return False
        return is_(self.distance).matches(edge["known"]["distance"])

    def describe_to(self, description):
        description.append("graph with {} {!r} and distance {} and blockedness {}".format(
            self.edge_type,
            " ".join((self.from_node, self.to_node)),
            self.distance,
            self.blockedness
        ))


class HasNode(hamcrest.base_matcher.BaseMatcher):

    node = anything()
    node_value = None

    def with_node(self, node):
        self.node = node
        return self

    def with_value(self, **kwargs):
        self.node_value = kwargs
        return self

    def _matches(self, objects):
        node_group = self.node.rstrip("1234567890")
        node = objects.get(node_group, {}).get(self.node)
        if not node:
            return False
        return is_(self.node_value).matches(node)

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


def has_edge(from_node=None, to_node=None):
    matcher = HasEdge()
    if from_node is not None:
        matcher.from_(from_node)
    if to_node is not None:
        matcher.to(to_node)
    return matcher
