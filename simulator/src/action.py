from decimal import Decimal
from functools import total_ordering
from logger import StyleAdapter
import logging

log = StyleAdapter(logging.getLogger(__name__))

_no_match = object()

@total_ordering
class Action(object):

	_ordinal = 2

	def __init__(self, start_time, duration, partial=None):
		self.start_time = start_time
		self.duration = duration
		if partial is not None:
			self.partial = partial

	def __eq__(self, other):
		return type(self) == type(other) and self.__dict__ == other.__dict__

	def __lt__(self, other):
		return self._ordinal < other._ordinal

	@property
	def end_time(self):
		return self.start_time + self.duration

	def partially_apply(self, model, deadline):
		raise NotImplementedError("{} cannot be partially applied".format(self))

	def __str__(self):
		return self._format(False)
	def __repr__(self):
		return self._format(True)

	def _format_pair(self, key, value, _repr):
		if not _repr and type(value) is Decimal:
			return "{}={!s}".format(key, value)
		else:
			return "{}={!r}".format(key, value)

	_format_key_order = "agent", "agent0", "agent1", "start_time", "duration", "node", "room", "start_node", "end_node", "partial", "execution_state"

	def _format(self, _repr):
		return "{}({})".format(self.__class__.__name__,
			", ".join(self._format_pair(k, getattr(self, k), _repr) for k in
				sorted(vars(self).keys(), key=self._format_key_order.index) if k != "execution_state")
		)

class Plan(Action):
	def __init__(self, start_time, duration):
		super(Plan, self).__init__(start_time, duration)
		self.agent = "planner"

class Stalled(Action):
	def __init__(self, start_time, duration, agent):
		super(Stalled, self).__init__(start_time, duration)
		self.agent = agent

class Move(Action):

	_ordinal = 0

	def __init__(self, start_time, duration, agent, start_node, end_node, partial=None):
		super(Move, self).__init__(start_time, duration, partial)
		self.agent = agent
		self.start_node = start_node
		self.end_node = end_node

	def is_applicable(self, model):
		return model["agents"][self.agent]["at"][1] == self.start_node

	def apply(self, model):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		model["agents"][self.agent]["at"][1] = self.end_node
		if self.start_node.startswith("temp"):
			del model["nodes"][self.start_node]
			model["graph"]["edges"] =  [edge for edge in model["graph"]["edges"] if self.start_node not in edge]


	def partially_apply(self, model, deadline):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		# create temp node
		continued_partial_move = self.start_node.startswith("temp")
		if continued_partial_move:
			action = self.modify_temp_node(model, deadline)
		else:
			action = self.create_temp_node(model, deadline)
		return action

	def modify_temp_node(self, model, deadline):
		temp_node_name = self.start_node

		back_edge, forward_edge = (edge for edge in model["graph"]["edges"] if edge[0] == temp_node_name)

		if forward_edge[1] == self.end_node:
			distance_moved = deadline - self.start_time
		elif back_edge[1] == self.end_node:
			distance_moved = self.start_time - deadline

		back_edge[2] += distance_moved
		forward_edge[2] -= distance_moved

		# create partial action representing move
		action = Move(self.start_time, distance_moved, self.agent, temp_node_name, self.end_node)
		action.partial = True
		return action

	def create_temp_node(self, model, deadline):
		temp_node_name = "-".join(("temp", self.agent, self.start_node, self.end_node))
		if temp_node_name in model["nodes"] or any(edge for edge in model["graph"]["edges"] if edge[0] == temp_node_name):
			log.error("tried to insert {}, but already initialised", temp_node_name)
			assert False;
		model["nodes"][temp_node_name] = {"node": True}
		# set up edges -- only allow movement out of node
		distance_moved = deadline - self.start_time
		distance_remaining = self.end_time - deadline
		model["graph"]["edges"].append([temp_node_name, self.start_node, distance_moved])
		model["graph"]["edges"].append([temp_node_name, self.end_node, distance_remaining])
		# move agent to temp node
		model["agents"][self.agent]["at"][1] = temp_node_name
		# create partial action representing move
		action = Move(self.start_time, distance_moved, self.agent, self.start_node, temp_node_name)
		action.partial = True
		return action

class Observe(Action):

	_ordinal = 1

	def __init__(self, start_time, agent, node):
		super(Observe, self).__init__(start_time, 0)
		self.agent = agent
		self.node = node

	def is_applicable(self, model):
		return model["agents"][self.agent]["at"][1] == self.node

	def apply(self, model):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		# check if new knowledge
		rm_obj = model["nodes"][self.node]
		unknown = rm_obj.get("unknown")

		if unknown:
			rm_obj["known"].update((k, self._get_actual_value(v)) for k, v in unknown.items())
			result = self._check_new_knowledge(unknown, model["assumed-values"])
			unknown.clear()
			return result

		return False

	@classmethod
	def _get_actual_value(cls, value):
		actual = value["actual"] # sometimes procduces a key refering to another value in `value'
		return actual if actual not in value else value[actual]

	def _check_new_knowledge(self, unknown_values, assumed_values):
		for key, unknown_value in unknown_values.items():
			assumed_value = assumed_values[key]
			if unknown_value["actual"] not in (assumed_value, unknown_value.get(assumed_value, _no_match)):
				return True
		return False


class Clean(Action):

	def __init__(self, start_time, duration, agent, room, partial=None):
		super(Clean, self).__init__(start_time, duration, partial)
		self.agent = agent
		self.room = room

	def is_applicable(self, model):
		return (
			model["agents"][self.agent]["at"][1] == self.room
			and model["nodes"][self.room]["known"].get("dirty", False)
			and not model["nodes"][self.room]["known"].get("extra-dirty", True)
		)

	def apply(self, model):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		rm_obj = model["nodes"][self.room]["known"]
		del rm_obj["dirtiness"]
		del rm_obj["dirty"]
		rm_obj["cleaned"] = True
		return False

	def partially_apply(self, model, deadline):
		assert self.is_applicable(model), "tried to apply action in an invalid state"

		max_duration = deadline - self.start_time
		node_state = model["nodes"][self.room]["known"]
		partial = node_state["dirtiness"] > max_duration

		if partial:
			node_state["dirtiness"] -= max_duration
			duration = max_duration
		else:
			duration = node_state["dirtiness"]
			log.info("{} applied partially, but able to fully complete in {}", self, duration)
			self.apply(model)

		action = Clean(self.start_time, duration, self.agent, self.room)
		action.partial = partial
		return action


class ExtraClean(Action):

	def __init__(self, start_time, duration, agent0, agent1, room, partial=None):
		super(ExtraClean, self).__init__(start_time, duration, partial)
		self.room = room
		self.agent0 = agent0
		self.agent1 = agent1

	def is_applicable(self, model):
		return (
			model["agents"][self.agent0]["at"][1] == self.room
			and model["agents"][self.agent1]["at"][1] == self.room
			and model["nodes"][self.room]["known"].get("extra-dirty", False)
			and not model["nodes"][self.room]["known"].get("dirty", True)
		)

	def apply(self, model):
		assert self.is_applicable(model), "tried to apply action in an invalid state"
		rm_obj = model["nodes"][self.room]["known"]
		del rm_obj["extra-dirty"]
		del rm_obj["dirtiness"]
		rm_obj["cleaned"] = True
		return False

	def partially_apply(self, model, deadline):
		assert self.is_applicable(model), "tried to apply action in an invalid state"

		max_duration = deadline - self.start_time
		node_state = model["nodes"][self.room]["known"]
		partial = node_state["dirtiness"] > max_duration

		if partial:
			node_state["dirtiness"] -= max_duration
			duration = max_duration
		else:
			duration = node_state["dirtiness"]
			log.info("{} applied partially, but able to fully complete in {}", self, duration)
			self.apply(model)

		action = ExtraClean(self.start_time, duration, self.agent0, self.agent1, self.room)
		action.partial = partial
		return action