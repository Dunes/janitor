__author__ = 'jack'

from markettaskallocation.common.goal import Goal
from markettaskallocation.common.problem_encoder import PddlGoal, ProblemEncoder
from pddl_parser import PlanDecoder, create_action_map
from . import action


__all__ = ["plan_decoder", "problem_encoder"]


class TrucksPddlGoal(PddlGoal):

	@staticmethod
	def is_main_goal(goal: Goal) -> bool:
		return True
		raise NotImplementedError
		return goal.predicate[0] == "cleaned"

	@property
	def explicit_deadline(self):
		return False
		raise NotImplementedError

	def as_sub_goal(self, goal: Goal, required_symbol: str):
		raise NotImplementedError
		return goal.predicate


problem_encoder = ProblemEncoder(TrucksPddlGoal, ("truck", "boat"))


plan_decoder = PlanDecoder(create_action_map(
	action.Load, action.Unload, action.Drive, action.Sail, action.DeliverOntime, action.DeliverAnytime
))