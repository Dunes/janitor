from abc import abstractmethod, ABCMeta
from typing import List, Dict
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
