from logging import getLogger
from copy import deepcopy
from decimal import Decimal
from typing import List

from logger import StyleAdapter
from accuracy import as_start_time, as_end_time, INSTANTANEOUS_ACTION_DURATION
from planner import Planner
from markettaskallocation.common.executor import AgentExecutor, EventExecutor, TaskAllocatorExecutor
from markettaskallocation.common.event import ObjectEvent
from markettaskallocation.common.goal import Goal, Task, Bid
from markettaskallocation.trucks.action import Action, DeliverAction, DeliverOntime, DeliverAnytime


__all__ = ["VehicleExecutor", "EventExecutor", "TaskAllocatorExecutor"]


__author__ = 'jack'
log = StyleAdapter(getLogger(__name__))


WON_NOTHING = "won-nothing"
WON_EXTRA_DIRTY_MAIN = "won-extra-dirty-main"  # TODO: modify these variables for trucks
WON_EXTRA_DIRTY_ASSIST = "won-extra-dirty-assist"


class VehicleExecutor(AgentExecutor):
	ignore_internal_events = False
	bidding_state = WON_NOTHING

	def extract_events_from_plan(self, plan: List[Action], goals: List[Goal]) -> List[ObjectEvent]:
		events = []
		for action_ in plan:
			# TODO: here goes any coordination between agents
			pass
			# if isinstance(action_, ExtraCleanAssist):
			# 	events.append(
			# 	 	ObjectEvent(
			# 		 	time=action_.start_time,
			# 		 	id_=action_.room,
			# 		 	predicates=[
			# 			 	Predicate(name="cleaning-assist", becomes=True, was=False),
			# 		 	],
			# 		 	hidden=False,
			# 		 	external=False,
			# 	 	)
			# 	)
			# 	events.append(
			# 	 	ObjectEvent(
			# 		 	time=as_start_time(action_.end_time),
			# 		 	id_=action_.room,
			# 		 	predicates=[
			# 			 	Predicate(name="cleaning-assist", becomes=False, was=True),
			# 		 	],
			# 		 	hidden=False,
			# 		 	external=False,
			# 	 	)
			# 	)
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

	def generate_bid(self, task: Task, planner: Planner, model, time, events) -> Bid:
		# if task.goal.predicate[0] not in ("cleaned", "cleaning-assisted"):
		# 	raise NotImplementedError("don't know how to accomplish {}".format(task.goal.predicate))

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

		if False:  # extra_dirty and not assist:  # TODO: re-add requirements for cooperation
			action = next(a for a in plan if isinstance(a, ExtraClean) and a.room == room_id)
			task_value = task.value / 2  # willing to share half the value with the other agent
			spare_time = task.goal.deadline - as_start_time(plan[-1].end_time)
			requirements = (
				Task(
					goal=Goal(
						predicate=("cleaning-assisted", room_id),
						deadline=action.start_time + spare_time,
						relative_earliest=action.start_time - self.planning_time - time,
					),
					value=task_value
				),
			)
		else:
			requirements = ()

		return Bid(
			agent=self.agent,
			estimated_endtime=as_start_time(plan[-1].end_time),
			additional_cost=self.compute_bid_value(task, plan, time),
			task=task,
			requirements=requirements,
			computation_time=time_taken
		)

	def convert_model_for_bid_generation(self, model):
		
		# need to try and force a way to see agents load packages correctly and this is passed trough to the planeer correctly
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
		raise RuntimeError("Not expecting trucks executor to have its plan effected by external knowledge")

	def new_plan(self, plan):
		# filter out deliver actions (these are performed by event executor
		new_plan = [action_ for action_ in plan if not isinstance(action_, DeliverAction)]
		super().new_plan(new_plan)

	def halt(self, time):
		super().halt(time)
		self.bidding_state = WON_NOTHING

	def notify_bid_won(self, bid: Bid, model):
		super().notify_bid_won(bid, model)
		# if bid.task.goal.predicate[0] == "cleaning-assisted":
		# 	assert self.bidding_state in (WON_EXTRA_DIRTY_ASSIST, WON_NOTHING)
		# 	self.bidding_state = WON_EXTRA_DIRTY_ASSIST
		# elif self.is_extra_dirty(bid.task.goal.predicate[1], model):
		# 	assert self.bidding_state in (WON_EXTRA_DIRTY_MAIN, WON_NOTHING)
		# 	self.bidding_state = WON_EXTRA_DIRTY_MAIN
