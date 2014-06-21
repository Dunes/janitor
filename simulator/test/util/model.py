'''
Created on 20 Jun 2014

@author: jack
'''

class ModelBuilder(object):

    def __init__(self):
        self.model = {"agents": {}, "nodes": {}, "graph": {"edges": []}}

    def _add_to(self, key, value, key_group):
        key_grp = self.model[key_group]
        key_grp[key] = value

    def with_agent(self, agent, at=None, available=None):
        agent_value = self._default_agent
        if at is not None: agent_value["at"] = [True, at]
        if available is not None: agent_value["available"] = available
        self._add_to(agent, agent_value, "agents")
        return self

    def with_node(self, node, value=None, not_room=None, **kwargs):
        if value is not None:
            node_value = value
        elif not_room:
            node_value = self._default_node
            node_value.update(kwargs)
        else:
            node_value = kwargs
            if "unknown" not in node_value:
                node_value["unknown"] = {}
            if "known" not in node_value:
                node_value["known"] = self._default_node
            node_value["known"]["is-room"] = True

        self._add_to(node, node_value, "nodes")
        return self

    def with_edge(self, from_node, to_node, distance):
        self.with_node(from_node, None)
        self.with_node(to_node, None)
        self.model["graph"]["edges"].append([from_node, to_node, distance])
        return self

    def with_assumed_values(self, values=None):
        self.model["assumed-values"] = values
        return self

    @property
    def _default_agent(self):
        return {
            "available": True,
            "agent": True,
            "at": [True, "n0"]
        }

    @property
    def _default_node(self):
        return {
            "node": True
        }
