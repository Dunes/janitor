__author__ = 'jack'

from action import Action as BaseAction, Plan, LocalPlan, GetExecutionHeuristic, as_end_time, \
    INSTANTANEOUS_ACTION_DURATION
from .problem_encoder import find_object
from planning_exceptions import ExecutionError

from itertools import chain
from abc import abstractmethod

from logger import StyleAdapter
from logging import getLogger

log = StyleAdapter(getLogger(__name__))

__all__ = ["Action", "Plan", "LocalPlan", "GetExecutionHeuristic", "Move", "Unblock", "Unload", "Load", "Rescue",
           "Observe"]


class Action(BaseAction):
    @abstractmethod
    def is_effected_by_change(self, id_):
        return False


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
        edge_id = self.start_node + " " + self.end_node
        other_edge_id = next(e_id for e_id in edges if e_id.startswith(temp_node_name) and e_id != edge_id)

        distance_moved = deadline - self.start_time

        edges[edge_id]["known"]["distance"] -= distance_moved
        edges[other_edge_id]["known"]["distance"] += distance_moved

        assert edges[edge_id]["known"]["distance"] > 0
        assert edges[other_edge_id]["known"]["distance"] > 0

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

    def is_effected_by_change(self, id_):
        return self.start_node in id_ and self.end_node in id_


class Unblock(Action):

    _format_attrs = ("start_time", "duration", "agent", "start_node", "end_node", "partial")

    def __init__(self, start_time, duration, agent, start_node, end_node, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "start_node", start_node)
        object.__setattr__(self, "end_node", end_node)

    def is_applicable(self, model):
        agent = model["objects"]["police"].get(self.agent)
        if agent is None:
            return False
        if agent["at"][1] not in (self.start_node, self.end_node):
            return False
        edge = model["graph"]["edges"][self.start_node + " " + self.end_node]
        return edge["known"].get("blocked-edge", False)

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        edge = model["graph"]["edges"][self.start_node + " " + self.end_node]["known"]
        inverse_edge = model["graph"]["edges"][self.end_node + " " + self.start_node]["known"]
        edge["edge"] = True
        del edge["blockedness"]
        del edge["blocked-edge"]
        inverse_edge["edge"] = True
        del inverse_edge["blockedness"]
        del inverse_edge["blocked-edge"]

    def partially_apply(self, model, deadline):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        edge = model["graph"]["edges"][self.start_node + " " + self.end_node]["known"]
        inverse_edge = model["graph"]["edges"][self.end_node + " " + self.start_node]["known"]
        edge["blockedness"] -= self.duration
        inverse_edge["blockedness"] -= self.duration


class Load(Action):

    _format_attrs = ("start_time", "duration", "agent", "target", "node", "partial")

    def __init__(self, start_time, duration, agent, target, node, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "node", node)

    def is_applicable(self, model):
        agent = model["objects"]["medic"].get(self.agent)
        if agent is None:
            return False
        if agent["at"][1] != self.node:
            return False
        carrying = agent.get("carrying")
        if carrying and carrying[1] != self.target:
            return False
        target = find_object(self.target, model["objects"])
        if self.node not in target["known"].get("at", ()):
            return False
        return agent["available"]

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        agent = model["objects"]["medic"][self.agent]
        del agent["empty"]
        agent["carrying"] = [True, self.target]
        target = find_object(self.target, model["objects"])
        del target["known"]["at"]

    def as_partial(self, end_time=None, **kwargs):
        if end_time is not None:
            assert "duration" not in kwargs
            assert end_time == self.end_time

        if "duration" in kwargs:
            assert kwargs["duration"] == self.duration

        obj = self.copy_with(**kwargs)
        return obj

    def partially_apply(self, model, deadline):
        raise NotImplementedError

    def is_effected_by_change(self, id_):
        return id_ in (self.node, self.target)


class Unload(Action):

    _format_attrs = ("start_time", "duration", "agent", "target", "node", "partial")

    def __init__(self, start_time, duration, agent, target, node, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "node", node)

    def is_applicable(self, model):
        agent = model["objects"]["medic"].get(self.agent)
        if agent is None:
            return False
        if agent["at"][1] != self.node:
            return False
        if agent.get("empty"):
            return False
        if not agent.get("available"):
            return False
        return agent["carrying"][1] == self.target

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        agent = model["objects"]["medic"][self.agent]
        agent["empty"] = True
        del agent["carrying"]
        target = find_object(self.target, model["objects"])
        target["known"]["at"] = [True, self.node]

    def as_partial(self, end_time=None, **kwargs):
        if end_time is not None:
            assert "duration" not in kwargs
            assert end_time == self.end_time

        if "duration" in kwargs:
            assert kwargs["duration"] == self.duration

        obj = self.copy_with(**kwargs)
        return obj

    def partially_apply(self, model, deadline):
        raise NotImplementedError

    def is_effected_by_change(self, id_):
        return id_ in (self.node, self.target)


class Rescue(Action):

    _format_attrs = ("start_time", "duration", "agent", "target", "node", "partial")

    def __init__(self, start_time, duration, agent, target, node, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "node", node)

    def is_applicable(self, model):
        agent = model["objects"]["medic"].get(self.agent)
        if agent is None:
            return False
        if agent["at"][1] != self.node:
            return False
        target = find_object(self.target, model["objects"])
        if not target["known"].get("buried"):
            return False
        if self.node not in target["known"].get("at", ()):
            return False
        return agent["available"]

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        target = find_object(self.target, model["objects"])["known"]
        target["unburied"] = True
        del target["buried"]
        del target["buriedness"]

    def partially_apply(self, model, deadline):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        target = find_object(self.target, model["objects"])["known"]
        target["buriedness"] -= self.duration

    def is_effected_by_change(self, id_):
        return id_ in (self.node, self.target)

class Observe(Action):

    _ordinal = 2

    _format_attrs = ("start_time", "agent", "node")

    _default_at = None, None

    def __init__(self, observation_time, agent, node):
        super(Observe, self).__init__(as_end_time(observation_time), INSTANTANEOUS_ACTION_DURATION)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "node", node)

    def is_applicable(self, model):
        return find_object(self.agent, model["objects"])["at"][1] == self.node

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"

        # check if new knowledge
        changes = []
        # check to see if observe any objects
        for object_id, object_ in chain.from_iterable((v.items() for v in model["objects"].values())):
            unknown = object_.get("unknown")
            if unknown and object_["known"].get("at", self._default_at)[1] == self.node:
                object_["known"].update((k, self._get_actual_value(v)) for k, v in unknown.items())
                if self._check_new_knowledge(unknown, model["assumed-values"]):
                    changes.append(object_id)
                unknown.clear()

        # check to see if observe any edges
        for object_id, object_ in model["graph"]["edges"].items():
            unknown = object_.get("unknown")
            if unknown and self.node in object_id:
                object_["known"].update((k, self._get_actual_value(v)) for k, v in unknown.items())
                if self._check_new_knowledge(unknown, model["assumed-values"]):
                    changes.append(object_id)
                unknown.clear()

        return changes

    @staticmethod
    def _get_actual_value(value):
        actual = value["actual"]  # sometimes produces a key referring to another value in `value'
        return actual if actual not in value else value[actual]

    @staticmethod
    def _check_new_knowledge(unknown_values, assumed_values):
        no_match = object()
        for key, unknown_value in unknown_values.items():
            assumed_value = assumed_values[key]
            if unknown_value["actual"] not in (assumed_value, unknown_value.get(assumed_value, no_match)):
                return True
        return False

    def as_partial(self, **kwargs):
        return None

    def partially_apply(self, model, deadline):
        raise NotImplementedError
