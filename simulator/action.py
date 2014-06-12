from collections import namedtuple
from planning_exceptions import ExecutionError

ExecutionState = namedtuple("ExecutionState", "pre_start executing finished")("pre_start", "executing", "finished")

_no_match = object()

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
			rm_obj["known"].update((k,self._get_actual_value(v)) for k, v in unknown.iteritems())
			result = self._check_new_knowledge(unknown, model["assumed-values"])
			unknown.clear()
			return result
		
		return False
	
	@classmethod
	def _get_actual_value(cls, value):
		actual = value["actual"] # sometimes procduces a key refering to another value in `value'
		return actual if actual not in value else value[actual]
	
	def _check_new_knowledge(self, unknown_values, assumed_values):
		for key, unknown_value in unknown_values.iteritems():
			assumed_value = assumed_values[key]
			if unknown_value["actual"] not in (assumed_value, unknown_value.get(assumed_value, _no_match)):
				return True
		return False
		
		
class Clean(Action):

	def __init__(self, start_time, duration, (agent, room)):
		super(Clean, self).__init__(start_time, duration)
		self.agent = agent
		self.room = room
		
	def apply(self, model):
		rm_obj = model["nodes"][self.room]["known"]
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
