from markettaskallocation.common.action import Action, Plan, LocalPlan, GetExecutionHeuristic, Observe, EventAction, \
    Allocate
from markettaskallocation.common.problem_encoder import find_object
from planning_exceptions import ExecutionError

from logger import StyleAdapter
from logging import getLogger

log = StyleAdapter(getLogger(__name__))

__all__ = ["Action", "Plan", "LocalPlan", "GetExecutionHeuristic", "Move", "Unblock", "Unload", "Load", "Rescue",
           "Observe", "Allocate", "EventAction", "Clear", "REAL_ACTIONS"]


class Move(Action):
    """
    :type agent: str
    :type start_node: str
    :type end_node: str
    """
    agent = None
    start_node = None
    end_node = None

    _format_attrs = ("start_time", "duration", "agent", "start_node", "end_node", "partial")

    def __init__(self, start_time, duration, agent, start_node, end_node, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "start_node", start_node)
        object.__setattr__(self, "end_node", end_node)

    @property
    def edge(self):
        return " ".join((self.start_node, self.end_node))

    def is_applicable(self, model):
        return find_object(self.agent, model["objects"])["at"][1] == self.start_node \
            and (model["graph"]["edges"][self.edge]["known"].get("edge") or
                 getattr(self, "partial", False))

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        find_object(self.agent, model["objects"])["at"][1] = self.end_node
        if self.start_node.startswith("temp"):
            del model["objects"]["building"][self.start_node]
            edge_ids = [edge_id for edge_id in model["graph"]["edges"] if edge_id.startswith(self.start_node)]
            for edge_id in edge_ids:
                del model["graph"]["edges"][edge_id]
        return False

    def partially_apply(self, model, deadline):
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
        edge_id = self.edge
        other_edge_id = next(e_id for e_id in edges if e_id.startswith(temp_node_name) and e_id != edge_id)

        distance_moved = deadline - self.start_time

        edges[edge_id]["known"]["distance"] -= distance_moved
        edges[other_edge_id]["known"]["distance"] += distance_moved

        assert edges[edge_id]["known"]["distance"] > 0
        assert edges[other_edge_id]["known"]["distance"] > 0

    def create_temp_node(self, model, deadline):
        temp_node_name = "-".join(("temp", self.agent, self.start_node, self.end_node))
        if temp_node_name in model["objects"]["building"] or \
                temp_node_name in model["graph"]["edges"]:
            log.error("tried to insert {}, but already initialised", temp_node_name)
            raise ValueError("tried to insert {}, but already initialised".format(temp_node_name))
        model["objects"]["building"][temp_node_name] = {}
        # set up edges -- only allow movement out of node
        edge = self.get_edge(model, self.start_node, self.end_node)
        distance_moved = deadline - self.start_time
        distance_remaining = edge["known"]["distance"] - distance_moved
        blocked = not edge["known"].get("edge", False)
        model["graph"]["edges"].update(self._create_temp_edge_pair(temp_node_name, self.start_node, self.end_node,
            distance_moved, distance_remaining, blocked))
        # move agent to temp node
        find_object(self.agent, model["objects"])["at"][1] = temp_node_name

    @staticmethod
    def _create_temp_edge_pair(temp_node, start_node, end_node, moved, remaining, blocked):
        if not blocked or remaining < moved:
            yield (" ".join((temp_node, end_node)), {
                "known": {
                    "distance": remaining,
                    "edge": True,
                },
                "unknown": {}
            })
            if remaining < moved:
                return
        yield (" ".join((temp_node, start_node)), {
            "known": {
                "distance": moved,
                "edge": True,
            },
            "unknown": {}
        })

    def get_edge(self, model, start_node, end_node):
        edge_key = " ".join((start_node, end_node))
        try:
            return model["graph"]["edges"][edge_key]
        except KeyError:
            pass
        if model["graph"]["bidirectional"]:
            raise NotImplementedError
        raise ExecutionError("Could not find {!r}".format(edge_key))

    def is_effected_by_change(self, id_):
        return self.start_node in id_ and self.end_node in id_


class Unblock(Action):
    """
    :type agent: str
    :type start_node: str
    :type end_node: str
    """
    agent = None
    start_node = None
    end_node = None

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
        return True
        # edge = model["graph"]["edges"][self.start_node + " " + self.end_node]
        # return edge["known"].get("blocked-edge", False)

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        edge = model["graph"]["edges"][self.start_node + " " + self.end_node]["known"]
        inverse_edge = model["graph"]["edges"][self.end_node + " " + self.start_node]["known"]
        if edge["edge"]:
            log.info("{} attempting to unblock {} {} edge, which is already unblocked.", self.agent, self.start_node,
                     self.end_node)
            return
        edge["edge"] = True
        del edge["blockedness"]
        del edge["blocked-edge"]
        inverse_edge["edge"] = True
        if "blockedness" not in inverse_edge:
            pass
        del inverse_edge["blockedness"]
        del inverse_edge["blocked-edge"]

    def partially_apply(self, model, deadline):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        edge = model["graph"]["edges"][self.start_node + " " + self.end_node]["known"]
        inverse_edge = model["graph"]["edges"][self.end_node + " " + self.start_node]["known"]
        edge["blockedness"] -= self.duration
        inverse_edge["blockedness"] -= self.duration


class Load(Action):
    """
    :type agent: str
    :type target: str
    :type node: str
    """
    agent = None
    target = None
    node = None

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
    """
    :type agent: str
    :type target: str
    :type node: str
    """
    agent = None
    target = None
    node = None

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
        target["known"]["rescued"] = True

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
    """
    :type agent: str
    :type target: str
    :type node: str
    """
    agent = None
    target = None
    node = None

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


class Clear(Action):
    """
    Dummy action that represents achieving the goal of clearing an edge at a specific time

    This seems like a massive hack... Perhaps it returns None and is filtered out somehow.
    """

    def __new__(cls, start_time, duration, start_node, end_node, predicate):
        return None


REAL_ACTIONS = (Move, Unblock, Load, Unload, Rescue)
