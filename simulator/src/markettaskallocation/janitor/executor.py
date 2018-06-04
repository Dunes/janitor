from logging import getLogger
from copy import deepcopy
from decimal import Decimal
from typing import List, Dict

from logger import StyleAdapter
from accuracy import as_start_time
from planner import Planner
from markettaskallocation.common.executor import AgentExecutor, EventExecutor, TaskAllocatorExecutor
from markettaskallocation.common.event import ObjectEvent, Predicate
from markettaskallocation.common.goal import Goal, Task, Bid
from markettaskallocation.janitor.action import Move, Observe, Clean, ExtraClean, ExtraCleanAssist
from markettaskallocation.common.domain_context import DomainContext


__all__ = ["JanitorExecutor", "EventExecutor", "TaskAllocatorExecutor"]


__author__ = 'jack'
log = StyleAdapter(getLogger(__name__))


WON_NOTHING = "won-nothing"
WON_EXTRA_DIRTY_MAIN = "won-extra-dirty-main"
WON_EXTRA_DIRTY_ASSIST = "won-extra-dirty-assist"

MIN_DURATION_EXTENSION_TO_ALLOW_PLANNER_SUCCESS = Decimal('0.001')


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
    ignore_internal_events = False
    bidding_state = WON_NOTHING

    def extract_events(self, plan, goals):
        """

        :param plan: list[Action]
        :param goals: list[Goal]
        :return: list[Event]
        """
        events = []
        for action_ in plan:
            if isinstance(action_, ExtraCleanAssist):
                events.append(
                    ObjectEvent(
                        time=action_.start_time,
                        id_=action_.room,
                        predicates=[
                            Predicate(name="cleaning-assist", becomes=True),
                        ],
                        hidden=False,
                        external=False,
                    )
                )
                events.append(
                    ObjectEvent(
                        time=action_.start_time + action_.duration + MIN_DURATION_EXTENSION_TO_ALLOW_PLANNER_SUCCESS,
                        id_=action_.room,
                        predicates=[
                            Predicate(name="cleaning-assist", becomes=False, was=True),
                        ],
                        hidden=False,
                        external=False,
                    )
                )
        return events

    def generate_bid(self, task: Task, planner: Planner, model, time, events) -> Bid:
        if task.goal.predicate[0] not in ("cleaned", "cleaning-assisted"):
            raise NotImplementedError("don't know how to accomplish {}".format(task.goal.predicate))

        assist = task.goal.predicate[0] == "cleaning-assisted"
        room_id = task.goal.predicate[1]
        extra_dirty = self.is_extra_dirty(room_id, model)
        if extra_dirty:
            if assist and self.bidding_state == WON_EXTRA_DIRTY_MAIN:
                return None
            elif not assist and self.bidding_state == WON_EXTRA_DIRTY_ASSIST:
                return None

        plan, time_taken = planner.get_plan_and_time_taken(
            model=self.convert_model_for_bid_generation(model, room_id, extra_dirty, assist),
            duration=self.planning_time,
            agent=self.agent,
            goals=[task.goal] + [b.task.goal for b in self.won_bids],
            metric=None,
            time=time,
            events=events
        )
        if plan is None:
            return None

        if extra_dirty and not assist:
            action = next(a for a in plan if isinstance(a, ExtraClean) and a.room == room_id)
            task_value = task.value / 2  # willing to share half the value with the other agent
            spare_time = task.goal.deadline - as_start_time(plan[-1].end_time)
            requirements = (
                Task(
                    goal=Goal(
                        predicate=("cleaning-assisted", room_id),
                        deadline=action.start_time + spare_time,
                    ),
                    value=task_value
                ),
            )
        else:
            requirements = ()

        return Bid(agent=self.agent,
                   estimated_endtime=as_start_time(plan[-1].end_time),
                   additional_cost=self.compute_bid_value(task, plan, time),
                   task=task,
                   requirements=requirements,
                   computation_time=time_taken)

    def convert_model_for_bid_generation(self, model, room_id: str, extra_dirty: bool, assist: bool):
        model = deepcopy(model)
        if self.bidding_state == WON_EXTRA_DIRTY_MAIN or (extra_dirty and not assist):
            assert self.bidding_state != WON_EXTRA_DIRTY_ASSIST
            self._add_assisted_clean_predicate(model)

        return model

    @staticmethod
    def _add_assisted_clean_predicate(model):
        for room in model["objects"]["room"].values():
            known = room["known"]
            if known.get("extra-dirty", False):
                known["cleaning-assist"] = True

    def transform_model_for_planning(self, model, goals):
        return deepcopy(model)

    def resolve_effected_plan(self, time, changed_id, effected):
        self.central_executor.notify_planning_failure(self.id, time)
        # goals = [bid.task.goal for bid in self.won_bids]
        # self.halt(time)new_pla
        # # No metric. Can either still complete all goals or not
        # self.new_plan([LocalPlan(as_start_time(time), self.central_executor.planning_time,
        #                          self.agent, goals=goals, metric=None)])
        # return

    def new_plan(self, plan):
        new_plan = []
        for action in plan:
            new_plan.append(action)
            if isinstance(action, Move):
                new_plan.append(Observe(action.end_time, action.agent, action.end_node))
        super().new_plan(new_plan)

    def halt(self, time):
        super().halt(time)
        self.bidding_state = WON_NOTHING

    def notify_bid_won(self, bid: Bid, model):
        super().notify_bid_won(bid, model)
        if bid.task.goal.predicate[0] == "cleaning-assisted":
            assert self.bidding_state in (WON_EXTRA_DIRTY_ASSIST, WON_NOTHING)
            self.bidding_state = WON_EXTRA_DIRTY_ASSIST
        elif self.is_extra_dirty(bid.task.goal.predicate[1], model):
            assert self.bidding_state in (WON_EXTRA_DIRTY_MAIN, WON_NOTHING)
            self.bidding_state = WON_EXTRA_DIRTY_MAIN

    @staticmethod
    def is_extra_dirty(room_id, model):
        room = model["objects"]["room"].get(room_id)
        if not room:
            raise TypeError('expected valid room id: got {}'.format(room_id))
        return room["known"].get("extra-dirty", False)
