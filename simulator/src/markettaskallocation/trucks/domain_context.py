from typing import List, Dict
from decimal import Decimal
from copy import deepcopy

from markettaskallocation.common.domain_context import DomainContext
from markettaskallocation.common.goal import Goal, Task


__all__ = ["TrucksDomainContext"]


class TrucksDomainContext(DomainContext):

    @property
    def goal_key(self):
        return "hard-goals"  # TODO: change to use soft goals (this is a big thing I think)

    def compute_tasks(self, model, time):
        goals = model["goal"][self.goal_key]
        value = Decimal(100000)

        tasks = []
        for g in goals:
            deadline = Decimal("inf")
            earliest = Decimal(0)
            t = Task(Goal(tuple(g), deadline, earliest), value)
            tasks.append(t)
        return tasks

    def get_metric_from_tasks(self, tasks: List[Task], base_metric: dict) -> Dict[Goal, Decimal]:
        metric = deepcopy(base_metric)
        assert "weight" not in metric
        metric["weights"] = {"total-time": 1, "soft-goal-violations": {task.goal: task.value for task in tasks}}
        return metric

    def get_agent(self, model, key):
        return self._try_get_object(model, ("truck", "boat"), key)

    def get_vehicle_area(self, model, key):
        return self._try_get_object(model, ("vehiclearea",), key)

    def get_node(self, model, key):
        return self._try_get_object(model, ("location",), key)

    def get_package(self, model, key):
        return self._try_get_object(model, ("package",), key)

    def task_key_for_allocation(self, task):
        return task.goal.deadline, task.goal.predicate

    @staticmethod
    def opposite_agent_type(type_):
        if type_ == "boat":
            return "truck"
        elif type_ == "truck":
            return "boat"
        else:
            raise ValueError("unrecognised agent type: {!r}".format(type_))
