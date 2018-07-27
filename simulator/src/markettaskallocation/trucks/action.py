from markettaskallocation.common.action import (
	Action, Plan, LocalPlan, GetExecutionHeuristic, Allocate, EventAction
)
from markettaskallocation.trucks.domain_context import TrucksDomainContext
from markettaskallocation.common.problem_encoder import find_object
from planning_exceptions import ExecutionError

from logger import StyleAdapter
from logging import getLogger
from decimal import Decimal
from abc import ABCMeta, abstractmethod

log = StyleAdapter(getLogger(__name__))

__all__ = [
	"Action", "Plan", "LocalPlan", "GetExecutionHeuristic",
	"Drive", "Sail", "Load", "Unload", "DeliverOntime", "DeliverAnytime", "DeliverMultiple",
	"Allocate", "EventAction", "REAL_ACTIONS", "DeliverAction"
]

ZERO = Decimal(0)
DOMAIN_CONTEXT = TrucksDomainContext()


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

	def apply(self, model):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		model["objects"][self.agent_type][self.agent]["at"][1] = self.end_node
		if self.start_node.startswith("temp"):
			del model["objects"]["node"][self.start_node]
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

	def is_effected_by_change(self, id_):
		return self.start_node in id_ and self.end_node in id_


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

	def is_effected_by_change(self, id_):
		raise RuntimeError


class Unload(Action):
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

	def is_effected_by_change(self, id_):
		return id_ in (self.node, self.target)


class DeliverAction(Action):  # abstract base class
	"""
	:type agent: str
	:type package: str
	:type location: str
	"""
	agent = None
	package = None
	location = None

	_format_attrs = ("start_time", "duration", "agent", "package", "location", "partial")

	def __init__(self, start_time, duration, agent, package, location, partial=None):
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

	def is_effected_by_change(self, id_):
		raise RuntimeError("expect no new knowledge in trucks domain")


class DeliverOntime(DeliverAction):

	def is_applicable(self, model):
		package = DOMAIN_CONTEXT.get_package(model, self.package)
		return package["at"][1] == self.location and package.get("deliverable", False)

	def apply(self, model):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		package = DOMAIN_CONTEXT.get_package(model, self.package)
		del package["at"]
		package["at-destination"] = [True, self.location]
		package["delivered"] = [True, self.location]


class DeliverAnytime(DeliverAction):

	def is_applicable(self, model):
		package = DOMAIN_CONTEXT.get_package(model, self.package)
		return package["at"][1] == self.location

	def apply(self, model):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		package = DOMAIN_CONTEXT.get_package(model, self.package)
		del package["at"]
		package["at-destination"] = [True, self.location]


class DeliverMultiple(Action):
	"""
	:type agent: str
	:type deliver_actions: list[DeliverAction]
	:type location: str
	"""
	agent = None
	deliver_actions = None
	location = None

	_format_attrs = ("start_time", "duration", "agent", "deliver_actions", "location", "partial")

	def __init__(self, start_time, duration, agent, deliver_actions, location, partial=None):
		super().__init__(start_time, duration, partial)
		object.__setattr__(self, "agent", agent)
		object.__setattr__(self, "deliver_actions", deliver_actions)
		object.__setattr__(self, "location", location)

	def is_applicable(self, model):
		return all(action.is_applicable(model) for action in self.deliver_actions)

	def apply(self, model):
		for action in self.deliver_actions:
			action.apply(model)

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

	def is_effected_by_change(self, id_):
		raise RuntimeError("expect no new knowledge in trucks domain")


REAL_ACTIONS = Drive, Sail, Load, Unload, DeliverOntime, DeliverAnytime, DeliverMultiple


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
