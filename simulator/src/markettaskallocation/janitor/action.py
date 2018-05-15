from markettaskallocation.common.action import Action, Plan, LocalPlan, GetExecutionHeuristic, Observe, EventAction, \
	Allocate
from markettaskallocation.common.problem_encoder import find_object
from planning_exceptions import ExecutionError

from logger import StyleAdapter
from logging import getLogger
from decimal import Decimal

log = StyleAdapter(getLogger(__name__))

__all__ = [
	"Action", "Plan", "LocalPlan", "GetExecutionHeuristic", "Move", "Clean", "ExtraClean",
	"Observe", "Allocate", "EventAction", "REAL_ACTIONS",
]

ZERO = Decimal(0)


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
			and (
				model["graph"]["edges"][self.edge]["known"].get("edge")
				or getattr(self, "partial", False)
			)

	def apply(self, model):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		find_object(self.agent, model["objects"])["at"][1] = self.end_node
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

		edges[edge_id]["known"]["distance"] -= distance_moved
		edges[other_edge_id]["known"]["distance"] += distance_moved

		assert edges[edge_id]["known"]["distance"] > 0
		assert edges[other_edge_id]["known"]["distance"] > 0

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
		distance_remaining = edge["known"]["distance"] - distance_moved
		blocked = not edge["known"].get("edge", False)
		model["graph"]["edges"].update(self._create_temp_edge_pair(
			temp_node_name, self.start_node, self.end_node, distance_moved, distance_remaining, blocked
		))
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


class Clean(Action):
	"""
	:type agent: str
	:type room: str
	"""
	agent = None
	room = None

	_format_attrs = ("start_time", "duration", "agent", "room", "partial")

	def __init__(self, start_time, duration, agent, room, partial=None):
		super().__init__(start_time, duration, partial)
		object.__setattr__(self, "agent", agent)
		object.__setattr__(self, "room", room)

	def is_applicable(self, model):
		agent = model["objects"]["agent"].get(self.agent)
		if agent is None:
			return False
		if agent["at"][1] != self.room:
			return False
		room = model["objects"]["room"][self.room]["known"]
		if "dirty" not in room or not room["dirty"]:
			return False
		return True

	def apply(self, model):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		room = model["objects"]["room"][self.room]["known"]
		if room["cleaned"]:
			# TODO: Observe actions should mean that the agent should know the state of the "cleaned" predicate
			raise ValueError("{!r} attempting to clean {!r} room, which is already cleaned.".format(
				self.agent, self.room
			))
		room["cleaned"] = True
		room["dirtiness"] = ZERO
		del room["dirty"]

	def partially_apply(self, model, deadline):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		room = model["objects"]["room"][self.room]["known"]
		room["dirtiness"] -= self.duration
		assert room["dirtiness"] > 0

	def is_effected_by_change(self, id_):
		return self.room == id_


class ExtraClean(Action):
	"""
	:type agent1: str
	:type agent2: str
	:type room: str
	"""
	agent1 = None
	agent2 = None
	room = None

	_format_attrs = ("start_time", "duration", "agent1", "agent2", "room", "partial")

	def __init__(self, start_time, duration, agent1, agent2, room, partial=None):
		super().__init__(start_time, duration, partial)
		object.__setattr__(self, "agent1", agent1)
		object.__setattr__(self, "agent2", agent2)
		object.__setattr__(self, "room", room)

	def is_applicable(self, model):
		for agent_str in self.agents():
			agent = model["objects"]["agent"].get(agent_str)
			if agent is None:
				return False
			if agent["at"][1] != self.room:
				return False
		room = model["objects"]["room"][self.room]["known"]
		if "extra-dirty" not in room or not room["extra-dirty"]:
			return False
		return True

	def apply(self, model):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		room = model["objects"]["room"][self.room]["known"]
		if room["cleaned"]:
			raise ValueError("{!r} attempting to clean {!r} room, which is already cleaned.".format(
				self.agent, self.room
			))
		room["cleaned"] = True
		room["dirtiness"] = ZERO
		del room["extra-dirty"]

	def partially_apply(self, model, deadline):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		room = model["objects"]["room"][self.room]["known"]
		room["dirtiness"] -= self.duration
		assert room["dirtiness"] > 0

	def agents(self) -> set:
		return {self.agent1, self.agent2}


REAL_ACTIONS = (Move, Clean, ExtraClean)
