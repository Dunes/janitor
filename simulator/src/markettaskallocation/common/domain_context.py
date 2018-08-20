from abc import abstractmethod, ABCMeta
from typing import List, Dict, Optional
from decimal import Decimal


from markettaskallocation.common.goal import Goal, Task


class DomainContext(metaclass=ABCMeta):

	@property
	@abstractmethod
	def goal_key(self) -> str:
		raise NotImplementedError

	@abstractmethod
	def compute_tasks(self, model, time: Decimal) -> List[Task]:
		raise NotImplementedError

	@abstractmethod
	def get_metric_from_tasks(self, tasks: List[Task], base_metric: dict) -> Dict[Goal, Decimal]:
		raise NotImplementedError

	@abstractmethod
	def get_agent(self, model, key):
		raise NotImplementedError

	@abstractmethod
	def get_node(self, model, key):
		raise NotImplementedError

	@abstractmethod
	def task_key_for_allocation(self, task):
		raise NotImplementedError

	@staticmethod
	def _try_get_object(model, types, key):

		for type_ in types:
			dict_ = model["objects"][type_]
			try:
				return dict_[key]
			except KeyError:
				pass
		raise KeyError(key)

	def disallowed_requirements(self, goal: Goal) -> Optional[set]:
		return None
