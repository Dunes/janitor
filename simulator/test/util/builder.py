'''
Created on 20 Jun 2014

@author: jack
'''
from inspect import getargspec

from action import Move, Clean, ExtraClean
from util.accuracy import quantize
from collections import OrderedDict

class ModelBuilder(object):

    def __init__(self, ordered=False):
        dict_type = OrderedDict if ordered else dict
        self.model = {"agents": dict_type(), "nodes": dict_type(), "graph": {"edges": []}}

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

class ActionBuilder(object):

    def __init__(self):
        self.params = {
            "agent": object(),
            "start_time": object(),
            "duration": object(),
            "start_node": object(),
            "end_node": object(),
            "room": object()
        }

    def agent(self, agent="agent"):
        self.params["agent"] = agent
        return self

    def agents(self, agent0="agent0", agent1="agent1"):
        self.params["agent0"] = agent0
        self.params["agent1"] = agent1
        return self

    def start_time(self, start_time=0):
        self.params["start_time"] = quantize(start_time)
        return self

    def duration(self, duration=0):
        self.params["duration"] = quantize(duration)
        return self

    def end_time(self, end_time=0):
        self.params["start_time"] = quantize(0)
        self.params["duration"] = quantize(end_time)
        return self

    def end_node(self, end_node="end_node"):
        self.params["end_node"] = end_node
        return self

    def start_node(self, start_node="start_node"):
        self.params["start_node"] = start_node
        return self

    def partial(self):
        self.params["partial"] = True
        return self


    def move(self):
        return Move(**{key: self.params.get(key) for key in getargspec(Move).args[1:]})

    def clean(self):
        return Clean(**{key: self.params.get(key) for key in getargspec(Clean).args[1:]})

    def extra_clean(self):
        return ExtraClean(**{key: self.params.get(key) for key in getargspec(ExtraClean).args[1:]})

