__author__ = 'jack'

from markettaskallocation.common.goal import Goal
from markettaskallocation.common.problem_encoder import PddlGoal, ProblemEncoder
from pddl_parser import PlanDecoder, create_action_map
from . import action


__all__ = ["plan_decoder", "problem_encoder"]


class JanitorPddlGoal(PddlGoal):
	_SUB_GOAL_MAP = {
		# "extra-clean": ""
	}

	@staticmethod
	def is_main_goal(goal: Goal) -> bool:
		return goal.predicate[0] == "cleaned"

	@property
	def sub_goal_map(self):
		return self._SUB_GOAL_MAP


problem_encoder = ProblemEncoder(JanitorPddlGoal, ("agent",))


plan_decoder = PlanDecoder(create_action_map(
	action.Move, action.Clean, action.ExtraClean
))
