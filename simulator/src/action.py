from accuracy import as_end_time, INSTANTANEOUS_ACTION_DURATION
from domain_context import TrucksDomainContext
from problem_encoder import find_object
from planning_exceptions import ExecutionError

from functools import total_ordering, partial as partial_func
from logger import StyleAdapter
from logging import getLogger
from decimal import Decimal
from typing import Optional, List
from abc import ABCMeta, abstractmethod

log = StyleAdapter(getLogger(__name__))

__all__ = [
    "Action", "Plan", "LocalPlan", "GetExecutionHeuristic",
    "Drive", "Sail", "Load", "Unload", "DeliverOntime", "DeliverAnytime",
    "REAL_ACTIONS", "DeliverAction"
]

ZERO = Decimal(0)
DOMAIN_CONTEXT = TrucksDomainContext()


@total_ordering
class Action(object):

    _ordinal = 1

    def __init__(self, start_time, duration, partial=None):
        object.__setattr__(self, "start_time", start_time)
        object.__setattr__(self, "duration", duration)
        if partial is not None:
            object.__setattr__(self, "partial", partial)

    def __setattr__(self, key, value):
        raise TypeError("Action objects are immutable")

    def __delattr__(self, item):
        raise TypeError("Action objects are immutable")

    def __eq__(self, other):
        return type(self) is type(other) and self.__dict__ == other.__dict__

    def __lt__(self, other):
        if isinstance(other, Action):
            return self._ordinal < other._ordinal
        raise TypeError("Expected instance of Action, got: {}".format(type(other)))

    @property
    def end_time(self):
        return as_end_time(self.start_time + self.duration)

    def is_applicable(self, model):
        raise NotImplementedError()

    def apply(self, model):
        raise NotImplementedError()

    def partially_apply(self, model, deadline):
        raise NotImplementedError("{} cannot be partially applied".format(self))

    def __str__(self):
        return self._format(False)

    def __repr__(self):
        return self._format(True)

    @staticmethod
    def _format_pair(key, value, _repr):
        if not _repr and type(value) is Decimal:
            return "{}={!s}".format(key, value)
        else:
            return "{}={!r}".format(key, value)

    _format_attrs = ("start_time", "duration", "partial")

    def _format(self, _repr):
        return "{}({})".format(self.__class__.__name__,
            ", ".join(self._format_pair(attr, getattr(self, attr), _repr) for attr in
                self._format_attrs if hasattr(self, attr))
        )

    def agents(self) -> set:
        return {self.agent}

    def copy_with(self, **kwargs):
        assert "apply" not in vars(self)
        attributes = self.__dict__.copy()
        attributes.update(kwargs)
        return self.__class__(**attributes)

    def as_partial(self, end_time=None, **kwargs):
        if end_time is not None:
            assert "duration" not in kwargs
            assert end_time >= self.start_time
            kwargs["duration"] = end_time - self.start_time

        if kwargs.get("duration") == 0:
            return None

        obj = self.copy_with(partial=True, **kwargs)
        object.__setattr__(obj, "apply", partial_func(obj.partially_apply, deadline=obj.end_time))
        return obj


class Plan(Action):

    _ordinal = 3

    _format_attrs = ("start_time", "duration", "agent")

    agent = "planner"

    def __init__(self, start_time, duration, agent=None, plan=None):
        super(Plan, self).__init__(start_time, duration)
        object.__setattr__(self, "agent", agent if agent else Plan.agent)
        object.__setattr__(self, "plan", plan)

    def is_applicable(self, model):
        return True

    def apply(self, model):
        return self.plan


class LocalPlan(Plan):

    _format_attrs = ("start_time", "duration", "agent", "goals", "tils")

    def __init__(self, start_time, duration, agent=None, plan=None, *, goals, tils):
        super(Plan, self).__init__(start_time, duration)
        object.__setattr__(self, "agent", agent if agent else Plan.agent)
        object.__setattr__(self, "plan", plan)
        object.__setattr__(self, "goals", goals)
        object.__setattr__(self, "tils", tils)


class Stalled(Action):

    _format_attrs = ("start_time", "duration", "agent")

    def __init__(self, start_time, duration, agent):
        super(Stalled, self).__init__(start_time, duration)
        object.__setattr__(self, "agent", agent)


class GetExecutionHeuristic(Action):

    _format_attrs = ("start_time", "duration", "agent")

    def __init__(self, start_time, duration=Decimal(0), agent=None, plan=None):
        super(GetExecutionHeuristic, self).__init__(start_time, duration=duration)
        object.__setattr__(self, "agent", agent if agent else Plan.agent)
        object.__setattr__(self, "plan", plan)

    def is_applicable(self, model):
        return True

    def apply(self, model):
        return self.plan


class Move(Action, metaclass=ABCMeta):
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

    @property
    @abstractmethod
    def agent_type(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def edge_type(self) -> str:
        raise NotImplementedError

    def is_applicable(self, model):
        agents_of_type = model["objects"][self.agent_type]
        try:
            agent = agents_of_type[self.agent]
        except KeyError:
            raise AssertionError("agent of type {!r} attempted a {} action".format(self.agent_type, type(self).__name__))
        return agent["at"][1] == self.start_node \
            and (
                model["graph"]["edges"][self.edge].get(self.edge_type)
                or getattr(self, "partial", False)
            )

    def apply(self, model) -> Optional[List[str]]:
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        model["objects"][self.agent_type][self.agent]["at"][1] = self.end_node
        if self.start_node.startswith("temp"):
            del model["objects"]["node"][self.start_node]
            edge_ids = [edge_id for edge_id in model["graph"]["edges"] if edge_id.startswith(self.start_node)]
            for edge_id in edge_ids:
                del model["graph"]["edges"][edge_id]
        return None

    def partially_apply(self, model, deadline):
        # create temp node
        continued_partial_move = self.start_node.startswith("temp")
        if continued_partial_move:
            self.modify_temp_node(model, deadline)
        else:
            self.create_temp_node(model, deadline)
        return None

    def modify_temp_node(self, model, deadline):
        temp_node_name = self.start_node

        edges = model["graph"]["edges"]
        edge_id = self.edge
        other_edge_id = next(e_id for e_id in edges if e_id.startswith(temp_node_name) and e_id != edge_id)

        distance_moved = deadline - self.start_time

        edges[edge_id]["distance"] -= distance_moved
        edges[other_edge_id]["distance"] += distance_moved

        assert edges[edge_id]["distance"] > 0
        assert edges[other_edge_id]["distance"] > 0

    def create_temp_node(self, model, deadline):
        temp_node_name = "-".join(("temp", self.agent, self.start_node, self.end_node))
        if temp_node_name in model["objects"]["node"] \
                or temp_node_name in model["graph"]["edges"]:
            log.error("tried to insert {}, but already initialised", temp_node_name)
            raise ValueError("tried to insert {}, but already initialised".format(temp_node_name))
        model["objects"]["node"][temp_node_name] = {}
        # set up edges -- only allow movement out of node
        edge = self.get_edge(model, self.start_node, self.end_node)
        distance_moved = deadline - self.start_time
        distance_remaining = edge["distance"] - distance_moved
        blocked = not edge.get(self.edge_type, False)
        model["graph"]["edges"].update(self._create_temp_edge_pair(
            temp_node_name, self.start_node, self.end_node, distance_moved, distance_remaining, blocked
        ))
        # move agent to temp node
        find_object(self.agent, model["objects"])["at"][1] = temp_node_name

    def _create_temp_edge_pair(self, temp_node, start_node, end_node, moved, remaining, blocked):
        if not blocked or remaining < moved:
            yield (" ".join((temp_node, end_node)), {
                "travel-time": remaining,
                self.edge_type: True,

            })
            if remaining < moved:
                return
        yield (" ".join((temp_node, start_node)), {
            "travel-time": moved,
            self.edge_type: True,
        })

    def get_edge(self, model, start_node, end_node):
        edge_key = " ".join((start_node, end_node))
        try:
            return model["graph"]["edges"][edge_key]
        except KeyError:
            pass
        if model["graph"]["bidirectional"]:
            raise RuntimeError
        raise ExecutionError("Could not find {!r}".format(edge_key))

    def is_effected_by_change(self, model, id_):
        return False


class Drive(Move):

    @property
    def agent_type(self):
        return "truck"

    @property
    def edge_type(self):
        return "connected-by-land"


class Sail(Move):

    @property
    def agent_type(self):
        return "boat"

    @property
    def edge_type(self):
        return "connected-by-sea"


class Load(Action):
    """
    :type package: str
    :type agent: str
    :type area: str
    :type location: str
    """
    package = None
    agent = None
    area = None
    location = None

    _format_attrs = ("start_time", "duration", "package", "agent", "area", "location", "partial")

    def __init__(self, start_time, duration, package, agent, area, location, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "package", package)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "area", area)
        object.__setattr__(self, "location", location)

    def is_applicable(self, model):
        agent = DOMAIN_CONTEXT.get_agent(model, self.agent)
        package = DOMAIN_CONTEXT.get_package(model, self.package)
        if not (self.location == agent["at"][1] == package["at"][1]):
            return False
        area = DOMAIN_CONTEXT.get_vehicle_area(model, self.area)
        return can_load_area(model, area, self.agent)

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        area = DOMAIN_CONTEXT.get_vehicle_area(model, self.area)
        del area["free"]
        package = DOMAIN_CONTEXT.get_package(model, self.package)
        del package["at"]
        package["in"] = [True, self.agent, self.area]

    def as_partial(self, end_time=None, **kwargs):
        if end_time is not None:
            assert "duration" not in kwargs
            assert end_time == self.end_time

        if "duration" in kwargs:
            assert kwargs["duration"] == self.duration

        obj = self.copy_with(**kwargs)
        return obj

    def partially_apply(self, model, deadline):
        raise RuntimeError

    def is_effected_by_change(self, model, id_):
        return False


class Unload(Action):
    """
    :type package: str
    :type agent: str
    :type area: str
    :type location: str
    :type deliver_action: DeliverAction
    """
    package = None
    agent = None
    area = None
    location = None
    deliver_action = None

    _format_attrs = ("start_time", "duration", "package", "agent", "area", "location", "partial")

    def __init__(self, start_time, duration, package, agent, area, location, partial=None, deliver_action=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "package", package)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "area", area)
        object.__setattr__(self, "location", location)
        object.__setattr__(self, "deliver_action", deliver_action)

    def is_applicable(self, model):
        agent = DOMAIN_CONTEXT.get_agent(model, self.agent)
        package = DOMAIN_CONTEXT.get_package(model, self.package)
        if not self.location == agent["at"][1]:
            return False
        if not [True, self.agent, self.area] == package["in"]:
            return False
        area = DOMAIN_CONTEXT.get_vehicle_area(model, self.area)
        return can_unload_area(model, area, self.agent)

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        area = DOMAIN_CONTEXT.get_vehicle_area(model, self.area)
        area["free"] = [True, self.agent]
        package = DOMAIN_CONTEXT.get_package(model, self.package)
        package["at"] = [True, self.location]
        del package["in"]

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

    def is_effected_by_change(self, model, id_):
        return False


class DeliverAction(Action):  # abstract base class
    """
    :type agent: str
    :type package: str
    :type location: str
    """
    agent = None
    package = None
    location = None

    _ordinal = 1.5

    _format_attrs = ("start_time", "duration", "package", "location", "partial")

    def __init__(self, start_time, duration, package, location, partial=None, *, agent=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "package", package)
        object.__setattr__(self, "location", location)

    def is_applicable(self, model):
        raise NotImplementedError

    def apply(self, model):
        raise NotImplementedError

    def as_partial(self, end_time=None, **kwargs):
        if end_time is not None:
            assert "duration" not in kwargs
            assert end_time == self.end_time

        if "duration" in kwargs:
            assert kwargs["duration"] == self.duration

        obj = self.copy_with(**kwargs)
        return obj

    def partially_apply(self, model, deadline):
        raise RuntimeError


class DeliverOntime(DeliverAction):

    def is_applicable(self, model):
        package = DOMAIN_CONTEXT.get_package(model, self.package)
        return (
            "delivered" in package
            or (
                package["at"][1] == self.location
                and "deliverable" in package
            )
        )

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        package = DOMAIN_CONTEXT.get_package(model, self.package)
        package["at-destination"] = [True, self.location]
        package["delivered"] = [True, self.location]

    def is_effected_by_change(self, model, id_):
        if id_ != self.package:
            return False
        package = DOMAIN_CONTEXT.get_package(model, id_)
        return "delivered" not in package or "deliverable" not in package


class DeliverAnytime(DeliverAction):

    def is_applicable(self, model):
        package = DOMAIN_CONTEXT.get_package(model, self.package)
        return "at-destination" in package or package["at"][1] == self.location

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        package = DOMAIN_CONTEXT.get_package(model, self.package)
        package["at-destination"] = [True, self.location]


REAL_ACTIONS = Drive, Sail, Load, Unload, DeliverOntime, DeliverAnytime


def can_load_area(model, area, agent):
    while True:
        try:
            free_pred = area["free"]
        except KeyError:
            return False
        if free_pred[1] != agent:
            return False
        try:
            closer_pred = area["closer"]
        except KeyError:
            # this area is the closest and the path from this area to the given area was all free
            return True
        area = DOMAIN_CONTEXT.get_vehicle_area(model, closer_pred[0])


def can_unload_area(model, area, agent):
    if "free" in area:
        return False
    if "closer" not in area:
        return True
    # we can unload this area if we can load the area in front of it
    closer_area = DOMAIN_CONTEXT.get_vehicle_area(model, area["closer"][0])
    return can_load_area(model, closer_area, agent)
