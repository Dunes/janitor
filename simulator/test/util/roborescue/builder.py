__author__ = 'jack'

from inspect import getargspec
from collections import OrderedDict
from markettaskallocation.roborescue import action
from markettaskallocation.common.problem_encoder import find_object
from util.builder import ActionBuilder as ActionBuilderBase


class ModelBuilder(object):

    def __init__(self, ordered=False, bidirectional=True, assumed_values=None):
        dict_type = OrderedDict if ordered else dict
        self.model = {
            "objects": dict_type(),
            "graph": {"edges": dict_type()},
            "metric": {"weights": {"soft-goal-violations": dict_type()}}
        }
        self.bidirectional = bidirectional
        if assumed_values is not None:
            self.model["assumed-values"] = assumed_values

    def _add_to(self, key, value, *key_groups):
        assert key_groups
        key_grp = self.model
        for k in key_groups:
            key_grp = key_grp.setdefault(k, {})
        key_grp[key] = value

    def with_agent(self, agent, type=None, at=None, available=None, empty=None, carrying=None):
        agent_value = self._default_agent
        if at is not None:
            agent_value["at"] = [True, at]
        if available is not None:
            agent_value["available"] = available
        if empty is not None:
            agent_value["empty"] = empty
        if carrying is not None:
            agent_value["carrying"] = [True, carrying]
        if type is None:
            type = agent.rstrip("0123456789")
        self._add_to(agent, agent_value, "objects", type)
        return self

    def with_object(self, object_id, type=None, at=None, known=True, **kwargs):
        agent_value = self._default_object
        agent_value["known" if known else "unknown"].update(kwargs)
        if at is not None:
            agent_value["known"]["at"] = [True, at]
        if type is None:
            type = object_id.rstrip("0123456789")
        self._add_to(object_id, agent_value, "objects", type)
        return self

    def with_node(self, node, value=None, type=None, **kwargs):
        try:
            find_object(node, self.model["objects"])
            return self
        except KeyError:
            pass
        if type is None:
            type = node.rstrip("0123456789")
        if value is not None:
            node_value = value
        else:
            node_value = kwargs
            if "unknown" not in node_value:
                node_value["unknown"] = {}
            if "known" not in node_value:
                node_value["known"] = self._default_node

        self._add_to(node, node_value, "objects", type)
        return self

    def with_edge(self, from_node, to_node, distance=None, blockedness=None, type=None, known=True):
        self.with_node(from_node, type="building")
        self.with_node(to_node, type="building")
        if type is None:
            type = "edge" if blockedness is None else "blocked-edge"
        edge = self._default_edge(distance, blockedness, type, known)
        self.model["graph"]["edges"][from_node + " " + to_node] = edge
        if self.bidirectional:
            edge = self._default_edge(distance, blockedness, type, known)
            self.model["graph"]["edges"][to_node + " " + from_node] = edge
        return self

    def with_assumed_values(self, values=None):
        self.model["assumed-values"] = values
        return self

    @property
    def _default_agent(self):
        return {
            "available": True,
            "at": [True, "n0"]
        }

    @property
    def _default_node(self):
        return {}

    @property
    def _default_object(self):
        return {"known": {}, "unknown": {}}

    @staticmethod
    def _default_edge(distance, blockedness, type, known):
        edge = {
            "known": {"distance": distance},
            "unknown": {}
        }
        if blockedness is not None:
            if known:
                edge["known"].update({
                    "blockedness": blockedness,
                    "edge": type == "edge",
                    "blocked-edge": type == "blocked-edge"
                })
            else:
                edge["unknown"].update({
                    "blockedness": {"min": 0, "max": max(100, blockedness), "actual": blockedness},
                    "edge": {"actual": type == "edge"},
                    "blocked-edge": {"actual": type == "blocked-edge"}
                })
        elif type is not None:
            if known:
                edge["known"].update({
                    "edge": type == "edge",
                    "blocked-edge": type == "blocked-edge"
                })
            else:
                edge["unknown"].update({
                    "edge": {"actual": type == "edge"},
                    "blocked-edge": {"actual": type == "blocked-edge"}
                })

        return edge


class ActionBuilder(ActionBuilderBase):

    def __init__(self):
        self.params = {
            "agent": object(),
            "start_time": object(),
            "duration": object(),
            "start_node": object(),
            "end_node": object(),
            "target": object(),
            "node": object()
        }

    def agents(self, *args, **kwargs):
        raise NotImplementedError

    def target(self, target):
        self.params["target"] = target
        return self

    def node(self, node):
        self.params["node"] = node
        return self

    def move(self):
        return action.Move(**{key: self.params.get(key) for key in getargspec(action.Move).args[1:]})

    def unblock(self):
        return action.Unblock(**{key: self.params.get(key) for key in getargspec(action.Unblock).args[1:]})

    def load(self):
        return action.Load(**{key: self.params.get(key) for key in getargspec(action.Load).args[1:]})

    def unload(self):
        return action.Unload(**{key: self.params.get(key) for key in getargspec(action.Unload).args[1:]})

    def rescue(self):
        return action.Rescue(**{key: self.params.get(key) for key in getargspec(action.Rescue).args[1:]})
