from logging import getLogger
from copy import deepcopy
from decimal import Decimal
from typing import List, Dict

from logger import StyleAdapter
from accuracy import as_start_time
from planner import Planner
from markettaskallocation.common.event import Predicate, EdgeEvent, ObjectEvent
from markettaskallocation.common.executor import AgentExecutor, EventExecutor, TaskAllocatorExecutor
from markettaskallocation.common.goal import Goal, Task, Bid
from markettaskallocation.roborescue.action import Move, Unblock
from markettaskallocation.common.problem_encoder import find_object
from markettaskallocation.common.domain_context import DomainContext


__all__ = ["JanitorExecutor", "EventExecutor", "TaskAllocatorExecutor"]


__author__ = 'jack'
log = StyleAdapter(getLogger(__name__))


class JanitorDomainContext(DomainContext):

    @property
    def goal_key(self):
        return "hard-goals"

    def compute_tasks(self, model, time):
        goals = model["goal"][self.goal_key]
        value = Decimal(100000)
        objects = model["objects"]

        tasks = []
        for g in goals:
            room_id = g[1]
            room = self.get_node(model, room_id)
            if room["known"].get("cleaned"):
                # goal already achieved
                continue
            deadline = Decimal("inf")
            t = Task(Goal(tuple(g), deadline), value)
            tasks.append(t)
        return tasks

    def get_metric_from_tasks(self, tasks: List[Task], base_metric: dict) -> Dict[Goal, Decimal]:
        metric = deepcopy(base_metric)
        assert "weight" not in metric
        metric["weights"] = {"total-time": 1, "soft-goal-violations": {task.goal: task.value for task in tasks}}
        return metric

    def get_agent(self, model, key):
        return self._try_get_object(model, ("agent",), key)

    def get_node(self, model, key):
        return self._try_get_object(model, ("room", "node"), key)


class JanitorExecutor(AgentExecutor):

    type_ = "agent"
    ignore_internal_events = True

    def extract_events(self, plan, goals):
        """

        :param plan: list[Action]
        :param goals: list[Goal]
        :return: list[Event]
        """
        if not all(g.predicate[0] == "cleaned" for g in goals):
            raise NotImplementedError("don't know how to produce events for {}".format(
                list(g.predicate for g in goals if g.predicate[0] != "cleaned")
            ))
        return []

    def generate_bid(self, task: Task, planner: Planner, model, time, events) -> Bid:
        if "cleaned" not in task.goal.predicate:
            raise NotImplementedError("don't know how to accomplish {}".format(task.goal.predicate))
        plan, time_taken = planner.get_plan_and_time_taken(
            model=model,
            duration=self.planning_time,
            agent=self.agent,
            goals=[task.goal] + [b.task.goal for b in self.won_bids],
            metric=None,
            time=time,
            events=events
        )
        if plan is None:
            return None

        return Bid(agent=self.agent,
                   estimated_endtime=as_start_time(plan[-1].end_time),
                   additional_cost=self.compute_bid_value(task, plan, time),
                   task=task,
                   requirements=(),
                   computation_time=time_taken)

    def transform_model_for_planning(self, model, goals):
        return deepcopy(model)
