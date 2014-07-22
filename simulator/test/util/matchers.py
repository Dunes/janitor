'''
Created on 20 Jun 2014

@author: jack
'''

import hamcrest
from hamcrest import anything, equal_to

__all__ = ["has_agent", "has_edge", "has_node"]

class HasAgent(hamcrest.base_matcher.BaseMatcher):

    def with_agent(self, agent):
        self.agent_name = agent
        return self

    def at(self, at):
        self.at = at
        return self

    def _matches(self, model):
        if self.agent_name in model["agents"]:
            agent_state = model["agents"][self.agent_name]
            if "at" in agent_state and len(agent_state["at"]) == 2:
                return agent_state["at"][1] == self.at
        return False

    def describe_to(self, description):
        description.append("model with agent {!r} at {!r}".format(self.agent_name, self.at))

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

    def _matches(self, model):
        edge = [self.from_node, self.to_node, self.distance]
        return edge in model["graph"]["edges"]

    def describe_to(self, description):
        description.append("graph with edge {!r}".format([self.from_node, self.to_node, self.distance]))

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

def has_agent(agent):
    return HasAgent().with_agent(agent)

def has_edge():
    return HasEdge()