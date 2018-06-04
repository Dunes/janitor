__author__ = 'jack'

from markettaskallocation.common.goal import Goal
from markettaskallocation.common.problem_encoder import PddlGoal, ProblemEncoder
from pddl_parser import PlanDecoder, create_action_map
from . import action


__all__ = ["plan_decoder", "problem_encoder"]


class JanitorPddlGoal(PddlGoal):

	@staticmethod
	def is_main_goal(goal: Goal) -> bool:
		return goal.predicate[0] == "cleaned"

	@property
	def explicit_deadline(self):
		return False

	def as_sub_goal(self, goal: Goal, required_symbol: str):
		return goal.predicate


problem_encoder = ProblemEncoder(JanitorPddlGoal, ("agent",))


plan_decoder = PlanDecoder(create_action_map(
	action.Move, action.Clean, action.ExtraClean, action.ExtraCleanAssist
))
