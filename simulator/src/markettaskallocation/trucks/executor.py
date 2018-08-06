from logging import getLogger
from copy import deepcopy
from decimal import Decimal
from typing import List, Optional

from logger import StyleAdapter
from accuracy import as_start_time, as_end_time, INSTANTANEOUS_ACTION_DURATION
from planner import Planner
from markettaskallocation.common.executor import (
	AgentExecutor,
	EventExecutor,
	TaskAllocatorExecutor,
	WON_INDEPENDENT,
	WON_GOAL_WITH_REQUIREMENTS,
	WON_ASSIST_GOAL,
)
from markettaskallocation.common.event import ObjectEvent, Predicate
from markettaskallocation.common.goal import Goal, Task, Bid
from markettaskallocation.trucks.action import Action, DeliverAction, DeliverOntime, Unload
from markettaskallocation.trucks.domain_context import TrucksDomainContext


__all__ = ["VehicleExecutor", "EventExecutor", "TaskAllocatorExecutor"]


__author__ = 'jack'
log = StyleAdapter(getLogger(__name__))


HELPER_AGENT = "helper-agent"

DOMAIN_CONTEXT = TrucksDomainContext()


class VehicleExecutor(AgentExecutor):
	def __init__(
			self, *, agent, planning_time, plan=None, deadline=Decimal("Infinity"), central_executor_id=None,
			halted=False, type_: str):
		super().__init__(
			agent=agent, planning_time=planning_time, plan=plan, deadline=deadline,
			central_executor_id=central_executor_id, halted=halted
		)
		self.type_ = type_

	@property
	def ignore_internal_events(self) -> bool:
		return False

	def extract_events_from_plan(self, plan: List[Action], goals: List[Goal]) -> List[ObjectEvent]:
		goal_set = {g.predicate for g in goals}
		assert len(goals) == len(goal_set)
		events = []
		for action_ in plan:
			if isinstance(action_, Unload):
				goal_predicate = "at", action_.package, action_.location
				if goal_predicate not in goal_set:
					continue

				events.append(ObjectEvent(
					time=as_start_time(action_.end_time),
					id_=action_.package,
					predicates=[
						Predicate(name="at", becomes=[True, action_.location], was=False),
					],
					hidden=False,
					external=False,
				))
		return events

	def extract_common_actions_from_plan(self, plan: List[Action], goals: List[Goal]) -> List[Action]:
		common_actions = []
		for action_ in plan:
			if isinstance(action_, DeliverAction):
				# new action that occurs in the instant after the unload occurs
				new_action = action_.copy_with(
					agent="event_executor",
					start_time=as_end_time(action_.start_time),
					duration=INSTANTANEOUS_ACTION_DURATION
				)
				common_actions.append(new_action)
		return common_actions

	def generate_bid(self, task: Task, planner: Planner, model, time, events) -> Optional[Bid]:
		if task.goal.predicate[0] not in ("delivered", "at"):
			raise NotImplementedError("don't know how to accomplish {}".format(task.goal.predicate))

		if task.goal.predicate[0] == "delivered":
			assistable = self.bidding_state != WON_ASSIST_GOAL
		else:
			assert task.goal.predicate[0] == "at"
			if self.bidding_state == WON_GOAL_WITH_REQUIREMENTS:
				# this agent is already dependent on being assisted, it cannot assist others due to scheduling
				# inter-dependencies.
				return None
			assistable = False

		plan, time_taken = planner.get_plan_and_time_taken(
			model=self.convert_model_for_bid_generation(model, task, assistable),
			duration=self.planning_time,
			agent="all",
			agent_problem_name="{}-{}".format(self.agent, "-".join(task.goal.predicate)),
			goals=[task.goal] + [b.task.goal for b in self.won_bids],
			metric=self.get_bidding_metric(model["metric"], assistable),
			time=time,
			events=self.create_events_for_bid_generation(model, events, task.goal, time + self.planning_time),
			use_preferences=False,
		)
		if plan is None:
			return None

		requirements = ()
		if assistable:
			for action_ in plan:
				if isinstance(action_, Unload) and action_.agent == HELPER_AGENT:
					# we would need assistance to complete this bid
					task_value = task.value
					delivery_action = next(a for a in plan if isinstance(a, DeliverOntime) and a.package == task.goal.predicate[1])
					spare_time = task.goal.deadline - delivery_action.start_time
					requirements = (
						Task(
							goal=Goal(
								predicate=("at", action_.package, action_.location),
								deadline=as_start_time(action_.end_time) + spare_time,
								relative_earliest=as_start_time(action_.end_time) - self.planning_time - time,
							),
							value=task_value
						),
					)
					break

		return Bid(
			agent=self.agent,
			estimated_endtime=as_start_time(plan[-1].end_time),
			additional_cost=self.compute_bid_value(task, plan, time),
			task=task,
			requirements=requirements,
			computation_time=time_taken
		)

	@staticmethod
	def get_bidding_metric(main_metric, assistable):
		assert main_metric["type"] == "minimize"
		if assistable:
			return {
				"type": "minimize",
				"predicate": [
					"+", main_metric["predicate"], ["*", ["used-helper-agent", HELPER_AGENT], 100000]
				]
			}
		else:
			return main_metric

	def convert_model_for_bid_generation(self, model, task: Task, assistable: bool):
		package_id = task.goal.predicate[1]
		package = DOMAIN_CONTEXT.get_package(model, package_id)

		# values we expect not to modify
		converted_model = {
			"domain": "trucks-bidding",
			"problem": "generated-trucks-bidding",
			"assumed-values": model["assumed-values"],
			"graph": model["graph"],
			"objects": {
				"location": model["objects"]["location"],
			}

		}

		# add agents
		model_self = deepcopy(model["objects"][self.type_][self.agent])
		model_self["main-agent"] = True
		converted_model["objects"][self.type_] = {self.agent: model_self}

		if assistable:
			helper_agent = {
				"at": [True, package["at"][1]],
				"can-load": [True, package_id],
				"used-helper-agent": 0,
			}

			converted_model["objects"][DOMAIN_CONTEXT.opposite_agent_type(self.type_)] = {
				HELPER_AGENT: helper_agent,
			}

		# add helper-agent vehiclearea
		if assistable:
			converted_model["objects"]["vehiclearea"] = {
				"vehiclearea-{}".format(HELPER_AGENT): {
					"free": [True, HELPER_AGENT]
				}
			}
		else:
			converted_model["objects"]["vehiclearea"] = {}
		# add this agent's vehiclearea -- this is a bit of a hack :(
		for area_name, area in model["objects"]["vehiclearea"].items():
			if area_name.endswith(self.agent):
				converted_model["objects"]["vehiclearea"][area_name] = deepcopy(area)

		# add the packages relevant to this agent
		model_packages = model["objects"]["package"]
		converted_model["objects"]["package"] = my_packages = {package_id: package}
		for bid in self.won_bids:
			other_p_id = bid.task.goal.predicate[1]
			other_package = my_packages[other_p_id] = deepcopy(model_packages[other_p_id])
			if bid.requirements:
				other_package.pop("at", None)
				other_package.pop("in", None)

		return converted_model

	def create_events_for_bid_generation(
			self, model, global_events, goal: Goal, execution_start_time: Decimal) -> List[ObjectEvent]:
		events = []
		for bid in self.won_bids:
			for sub_task in bid.requirements:
				predicate_name, package_id, location_id = sub_task.goal.predicate
				assert predicate_name == "at"
				events.append(ObjectEvent(
					time=execution_start_time + goal.relative_earliest,
					id_=package_id,
					predicates=[
						Predicate(name=predicate_name, becomes=[True, location_id], was=False),
					],
					hidden=False,
					external=True,
				))

		return events

	def transform_model_for_planning(self, model, goals):
		planning_model = deepcopy(model)
		return planning_model

	def transform_events_for_planning(self, events, model, goals, execution_start_time):
		events = super().transform_events_for_planning(events, model, goals, execution_start_time)
		return events

	def resolve_effected_plan(self, time, changed_id, effected):
		raise RuntimeError("Not expecting trucks executor to have its plan effected by external knowledge")

	def new_plan(self, plan):
		# filter out deliver actions (these are performed by event executor
		new_plan = [action_ for action_ in plan if not isinstance(action_, DeliverAction)]
		super().new_plan(new_plan)

	def halt(self, time):
		super().halt(time)
		self.bidding_state = WON_INDEPENDENT

	def notify_bid_won(self, bid: Bid, model):
		super().notify_bid_won(bid, model)
		if bid.task.goal.predicate[0] == "at":
			assert self.bidding_state in (WON_ASSIST_GOAL, WON_INDEPENDENT)
			self.bidding_state = WON_ASSIST_GOAL
		elif bid.requirements:
			assert self.bidding_state in (WON_GOAL_WITH_REQUIREMENTS, WON_INDEPENDENT)
			self.bidding_state = WON_GOAL_WITH_REQUIREMENTS
