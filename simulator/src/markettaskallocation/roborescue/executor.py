from logging import getLogger
from copy import deepcopy
from decimal import Decimal

from logger import StyleAdapter
from accuracy import as_start_time
from planner import Planner
from markettaskallocation.common.event import Predicate, EdgeEvent, ObjectEvent
from markettaskallocation.common.executor import AgentExecutor, EventExecutor, TaskAllocatorExecutor
from markettaskallocation.common.goal import Goal, Task, Bid
from markettaskallocation.roborescue.action import Move, Unblock
from markettaskallocation.common.problem_encoder import find_object
from markettaskallocation.common.domain_context import DomainContext


__all__ = ["PoliceExecutor", "MedicExecutor", "EventExecutor", "TaskAllocatorExecutor", "RoborescueDomainContext"]


__author__ = 'jack'
log = StyleAdapter(getLogger(__name__))


class RoborescueDomainContext(DomainContext):

    @property
    def goal_key(self):
        return "soft-goals"

    def compute_tasks(self, model, time):
        goals = model["goal"][self.goal_key]
        value = model["metric"]["weights"]["soft-goal-violations"]["rescued"]
        events = model["events"]
        objects = model["objects"]

        tasks = []
        for g in goals:
            civ_id = g[1]
            civ = find_object(civ_id, objects)
            if civ["known"].get("rescued"):
                # goal already achieved
                continue
            for e in events:
                if e.id_ == civ_id and any((p.name == "alive" and p.becomes is False) for p in e.predicates):
                    deadline = e.time
                    break
            else:
                deadline = Decimal("inf")
            if deadline <= time:
                # deadline already elapsed -- cannot achieve this goal
                log.info("deadline for rescuing {!r} already elapsed".format(civ_id))
                continue
            t = Task(Goal(tuple(g), deadline), value)
            tasks.append(t)
        return tasks

    def get_metric_from_tasks(self, tasks, base_metric):
        metric = deepcopy(base_metric)
        violations = metric["weights"]["soft-goal-violations"]
        violations.update((task.goal, task.value) for task in tasks)
        return metric


class PoliceExecutor(AgentExecutor):

    type_ = "police"
    ignore_internal_events = True

    def extract_events(self, plan, goals):
        """

        :param plan: list[Action]
        :param goals: list[Goal]
        :return: list[Event]
        """
        events = []
        unblocks = [(a, {a.start_node, a.end_node}) for a in plan if isinstance(a, Unblock)]
        edges = set(frozenset(g.predicate[1:]) for g in goals)
        for edge in edges:
            start, end = edge
            for u, unblock_nodes in unblocks:
                if edge == unblock_nodes:
                    events.append(self.create_clear_edge_event(as_start_time(u.end_time), start, end))
                    events.append(self.create_clear_edge_event(as_start_time(u.end_time), end, start))
                    break
            else:
                log.debug("failed to achieve goal: no matching unblock for unblock goal: {}", edge)

        return events

    @staticmethod
    def create_clear_edge_event(time, start_node, end_node):
        return EdgeEvent(
            time=time,
            id_="{} {}".format(start_node, end_node),
            predicates=[
                Predicate(name="edge", becomes=True),
                Predicate(name="blocked-edge", becomes=False),
            ],
            hidden=False,
            external=False
        )

    def generate_bid(self, task: Task, planner: Planner, model, time, events) -> Bid:
        if "rescued" in task.goal.predicate:
            return None
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


class MedicExecutor(AgentExecutor):

    type_ = "medic"
    ignore_internal_events = False

    def extract_events(self, plan, goals):
        """

        :param plan: list[Action]
        :param goals: list[Goal]
        :return: list[Event]
        """
        # medic does not produce events for planning
        return []

    @staticmethod
    def create_rescue_civilian_event(time, civ_id):
        return ObjectEvent(
            time=time,
            id_=civ_id,
            predicates=[
                Predicate(name="rescued", becomes=True),
            ],
            hidden=False,
            external=False
        )

    @classmethod
    def convert_model_for_bid_generation(cls, model):
        model = dict(model, graph=deepcopy(model["graph"]))
        cls.remove_blocks_from_model(model)
        return model

    @staticmethod
    def remove_blocks_from_model(model):
        """
        converts all blocked roads to be clear
        :param model:
        :return:
        """
        for edge in model["graph"]["edges"].values():
            edge["known"] = {
                "edge": True,
                "blocked-edge": False,
                "distance": edge["known"]["distance"]
            }
        return model

    def generate_bid(self, task: Task, planner: Planner, model, time, events) -> Bid:
        if "edge" in task.goal.predicate:
            return None
        plan, time_taken = planner.get_plan_and_time_taken(
            model=self.convert_model_for_bid_generation(model),
            duration=self.planning_time,
            agent=self.agent,
            goals=[task.goal] + [b.task.goal for b in self.won_bids],
            metric=None,
            time=time - self.planning_time,  # instantaneous plan?
            events=events
        )
        if plan is None:
            return None

        # generate any edge clearing requirements needed
        model_edges = model["graph"]["edges"]
        blocked_edge_actions = [a for a in plan if isinstance(a, Move) and not model_edges[a.edge]["known"]["edge"]]
        bid_value = self.compute_bid_value(task, plan, time)
        if blocked_edge_actions:
            task_value = task.value / len(blocked_edge_actions)
            spare_time = task.goal.deadline - as_start_time(plan[-1].end_time)
            requirements = tuple(
                Task(goal=Goal(predicate=("edge", a.start_node, a.end_node),
                    deadline=a.start_time + spare_time), value=task_value)
                for a in blocked_edge_actions
            )
        else:
            requirements = ()

        return Bid(agent=self.agent,
                   estimated_endtime=as_start_time(plan[-1].end_time),
                   additional_cost=bid_value,
                   task=task,
                   requirements=requirements,
                   computation_time=time_taken)

    def transform_model_for_planning(self, model, goals):
        new_model = super().transform_model_for_planning(model, goals)
        civ_ids_to_keep = [goal.predicate[1] for goal in goals]
        new_model["objects"]["civilian"] = {civ_id: civ
                                            for civ_id, civ in model["objects"]["civilian"].items()
                                            if civ_id in civ_ids_to_keep}
        return new_model

    # def transform_events_for_planning(self, events, goals):
    #     new_events = []
    #     for e in events:
    #         if e.external:
    #             new_events.append(e)
    #         elif isinstance(e, EdgeEvent):
    #             new_events.append(e)
    #     return new_events
