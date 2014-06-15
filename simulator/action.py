from collections import namedtuple
from planning_exceptions import ExecutionError
from total_ordering import total_ordering
from operator import attrgetter

debug = True
def _error_when_debug():
	if debug:
		raise ExecutionError("tried to apply action in an invalid state")

@total_ordering(attrgetter("ordinal"))
class ExecutionState(object):
	def __init__(self, desc, ordinal):
		self.desc = desc
		self.ordinal = ordinal
	def __str__(self):
		return self.desc
	__repr__ = __str__

ExecutionState = namedtuple("_ExecutionState", "pre_start executing finished")(
	*(ExecutionState(desc,-ordinal) for ordinal, desc in enumerate(("pre_start", "executing", "finished")))
)

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
	
	def __str__(self):
		return self._format(False)
	def __repr__(self):
		return self._format(True)
	
	def _format_pair(self, key, value, _repr):
		if not _repr and type(value) is float and int(value) != value:
			return "{}={:.2f}".format(key, value)
		else:
			return "{}={!r}".format(key, value)
	
	_key_order = "agent", "agent0", "agent1", "start_time", "duration", "node", "room", "start_node", "end_node", "execution_state"
	
	def _format(self, _repr):
		try:
			return "{}({})".format(self.__class__.__name__,
				", ".join(self._format_pair(k,getattr(self,k),_repr) for k in 
					sorted(vars(self).keys(), key=self._key_order.index) if k != "execution_state")
			)
		except:
			import pdb; pdb.set_trace()
			raise

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

	def is_applicable(self, model):
		return model["agents"][self.agent]["at"][1] == self.start_node
	
	def apply(self, model):
		self.is_applicable(model) or _error_when_debug()
		model["agents"][self.agent]["at"][1] = self.end_node
	
class Observe(Action):
	
	def __init__(self, start_time, agent, node):
		super(Observe, self).__init__(start_time, 0)
		self.agent = agent
		self.node = node

	def is_applicable(self, model):
		return model["agents"][self.agent]["at"][1] == self.node
	
	def apply(self, model):
		self.is_applicable(model) or _error_when_debug()
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
		
	def is_applicable(self, model):
		return (
			model["agents"][self.agent]["at"][1] == self.room
			and not model["nodes"][self.room]["known"].get("extra-dirty", True)
		)
		
	def apply(self, model):
		self.is_applicable(model) or _error_when_debug()
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
		
	def is_applicable(self, model):
		return (
			model["agents"][self.agent0]["at"][1] == self.room
			and model["agents"][self.agent1]["at"][1] == self.room
			and not model["nodes"][self.room]["known"].get("dirty", True)
		)
				
	def apply(self, model):
		self.is_applicable(model) or _error_when_debug()
		rm_obj = model["nodes"][self.room]["known"]
		del rm_obj["extra-dirty"]
		del rm_obj["dirtiness"]
		rm_obj["cleaned"] = True
		return False
