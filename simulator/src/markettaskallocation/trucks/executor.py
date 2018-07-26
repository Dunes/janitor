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
from markettaskallocation.trucks.action import Action
from markettaskallocation.common.domain_context import DomainContext


__all__ = ["TruckExecutor", "EventExecutor", "TaskAllocatorExecutor", "TrucksDomainContext"]


__author__ = 'jack'
log = StyleAdapter(getLogger(__name__))


WON_NOTHING = "won-nothing"
WON_EXTRA_DIRTY_MAIN = "won-extra-dirty-main"  # TODO: modify these variables for trucks
WON_EXTRA_DIRTY_ASSIST = "won-extra-dirty-assist"

MIN_DURATION_EXTENSION_TO_ALLOW_PLANNER_SUCCESS = Decimal('0.500')


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

    def get_node(self, model, key):
        return self._try_get_object(model, ("location",), key)

    def task_key_for_allocation(self, task):
        return task.goal.deadline, task.goal.predicate


class VehicleExecutor(AgentExecutor):
    ignore_internal_events = False
    bidding_state = WON_NOTHING

    def extract_events_from_plan(self, plan: List[Action], goals: List[Goal]) -> List[ObjectEvent]:
        events = []
        for action_ in plan:
            pass
            # if isinstance(action_, ExtraCleanAssist):
            #     events.append(
            #         ObjectEvent(
            #             time=action_.start_time,
            #             id_=action_.room,
            #             predicates=[
            #                 Predicate(name="cleaning-assist", becomes=True, was=False),
            #             ],
            #             hidden=False,
            #             external=False,
            #         )
            #     )
            #     events.append(
            #         ObjectEvent(
            #             time=as_start_time(action_.end_time),
            #             id_=action_.room,
            #             predicates=[
            #                 Predicate(name="cleaning-assist", becomes=False, was=True),
            #             ],
            #             hidden=False,
            #             external=False,
            #         )
            #     )
        return events

    def generate_bid(self, task: Task, planner: Planner, model, time, events) -> Bid:
        # if task.goal.predicate[0] not in ("cleaned", "cleaning-assisted"):
        #     raise NotImplementedError("don't know how to accomplish {}".format(task.goal.predicate))

        plan, time_taken = planner.get_plan_and_time_taken(
            model=self.convert_model_for_bid_generation(model),
            duration=self.planning_time,
            agent=self.agent,
            goals=[task.goal] + [b.task.goal for b in self.won_bids],
            metric=None,
            time=time,
            events=events + self.create_events_for_bid_generation(model, task.goal, time + self.planning_time)
        )
        if plan is None:
            return None

        if False: # extra_dirty and not assist:
            action = next(a for a in plan if isinstance(a, ExtraClean) and a.room == room_id)
            task_value = task.value / 2  # willing to share half the value with the other agent
            spare_time = task.goal.deadline - as_start_time(plan[-1].end_time)
            requirements = (
                Task(
                    goal=Goal(
                        predicate=("cleaning-assisted", room_id), deadline=action.start_time + spare_time,
                        relative_earliest=action.start_time - self.planning_time - time,
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

    def convert_model_for_bid_generation(self, model):
        model = deepcopy(model)
        return model

    def create_events_for_bid_generation(self, model, goal: Goal, time: Decimal) -> List[ObjectEvent]:
        events = []
        # add events for new task
        # ...

        # add events for previously won tasks
        # events += self.events_from_goals(model, [bid.task.goal for bid in self.won_bids], time + self.planning_time)

        return events

    def transform_model_for_planning(self, model, goals):
        planning_model = deepcopy(model)
        return planning_model

    def transform_events_for_planning(self, events, model, goals, execution_start_time):
        events = super().transform_events_for_planning(events, model, goals, execution_start_time)
        return events

    def resolve_effected_plan(self, time, changed_id, effected):
        self.central_executor.notify_planning_failure(self.id, time)

    def new_plan(self, plan):
        super().new_plan(plan)

    def halt(self, time):
        super().halt(time)
        self.bidding_state = WON_NOTHING

    def notify_bid_won(self, bid: Bid, model):
        super().notify_bid_won(bid, model)
        # if bid.task.goal.predicate[0] == "cleaning-assisted":
        #     assert self.bidding_state in (WON_EXTRA_DIRTY_ASSIST, WON_NOTHING)
        #     self.bidding_state = WON_EXTRA_DIRTY_ASSIST
        # elif self.is_extra_dirty(bid.task.goal.predicate[1], model):
        #     assert self.bidding_state in (WON_EXTRA_DIRTY_MAIN, WON_NOTHING)
        #     self.bidding_state = WON_EXTRA_DIRTY_MAIN
