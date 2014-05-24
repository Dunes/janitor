from collections import namedtuple
from planning_exceptions import ExecutionError

ExecutionState = namedtuple("ExecutionState", "pre_start executing finished")("pre_start", "executing", "finished")

class Action(object):
	
	def __init__(self, start_time, duration):
		self.start_time = start_time
		self.duration = duration
		self.execution_state = ExecutionState.pre_start
	
	def start(self):
		if self.execution_state != ExecutionState.pre_start:
			raise ExecutionError("invalid state")
		self.execution_state = ExecutionState.executing
	
	def finish(self):
		print "finishing:", self
		if self.execution_state != ExecutionState.executing:
			raise ExecutionError("invalid state")
		self.execution_state = ExecutionState.finished
		

	@property
	def end_time(self):
		return self.start_time + self.duration
	
	def __repr__(self):
		
		return "{}({})".format(self.__class__.__name__,
			", ".join("{}={!r}".format(k,v) for k,v in self.__dict__.iteritems() if k != "execution_state")
		)

class Plan(Action):
	def __init__(self, start_time, duration):
		super(Plan, self).__init__(start_time, duration)
		self.agent = "planner"

class Move(Action):
	def __init__(self, start_time, duration, (agent, start_node, end_node)):
		super(Move, self).__init__(start_time, duration)
		self.agent = agent
		self.start_node = start_node
		self.end_node = end_node
	
	def apply(self, model):
		if model["agents"][self.agent]["at"][1] != self.start_node:
			raise ExecutionError("agent did not start in expected room")
		model["agents"][self.agent]["at"][1] = self.end_node
	
class Observe(Action):
	
	def __init__(self, start_time, agent, node):
		super(Observe, self).__init__(start_time, 0)
		self.agent = agent
		self.node = node
	
	def apply(self, model):
		# check if new knowledge
		rm_obj = model["nodes"][self.node]
		unknown = rm_obj.get("unknown")
		
		if unknown:
			rm_obj["known"].update((k,v["actual"]) for k, v in unknown.iteritems())
			result = self._check_new_knowledge(unknown, model["assumed-values"])
			unknown.clear()
			return result
		
		return False
	
	def _check_new_knowledge(self, unknown_values, assumed_values):
		for key, unknown_value in unknown_values.iteritems():
			assumed_value_key = assumed_values[key]
			assumed_value = unknown_value.get(assumed_value_key, assumed_value_key)
			if not assumed_value == unknown_value["actual"]:
				return True
		return False
		
		
class Clean(Action):

	def __init__(self, start_time, duration, (agent, room)):
		super(Clean, self).__init__(start_time, duration)
		self.agent = agent
		self.room = room
		
	def apply(self, model):
		rm_obj = model["nodes"][self.room]["known"]
		if rm_obj["extra-dirty"]:
			raise ExecutionError("cannot clean an extra-dirty room with Clean action")
		del rm_obj["not-extra-dirty"]
		del rm_obj["dirtiness"]
		del rm_obj["dirty"]
		rm_obj["cleaned"] = True
		return False
	

class ExtraClean(Action):

	def __init__(self, start_time, duration, (agent0, agent1, room)):
		super(ExtraClean, self).__init__(start_time, duration)
		self.room = room
		self.agent0 = agent0
		self.agent1 = agent1
		
	def apply(self, model):
		rm_obj = model["nodes"][self.room]["known"]
		del rm_obj["extra-dirty"]
		del rm_obj["dirtiness"]
		del rm_obj["dirty"]
		rm_obj["cleaned"] = True
		return False
	
class Load(Action):

	def __init__(self, start_time, duration, (agent, room)):
		super(Load, self).__init__(start_time, duration)
		self.agent = agent
		self.room = room
	
	def apply(self, model):
		agent_obj = model["agents"][self.agent]
		agent_obj["has-stock"] = True
		agent_obj["carrying"] = agent_obj["max-carry"]
		
		return False
	
class Unload(Action):

	def __init__(self, start_time, end_time, (agent, room)):
		super(Unload, self).__init__(start_time, end_time)
		self.agent = agent
		self.room = room
		
	def apply(self, model):
		rm_obj = model["nodes"][self.room]["known"]
		agent_obj = model["agents"][self.agent]
		stock_moved = min(agent_obj["carrying"], rm_obj["req-stock"])	
		
		agent_obj["carrying"] -= stock_moved
		rm_obj["req-stock"] -= stock_moved
		
		if not agent_obj["carrying"]:
			agent_obj["has-stock"] = False
		
		if not rm_obj["req-stock"]:
			rm_obj["under-stocked"] = False
			rm_obj["fully-stocked"] = True
		
		return False
