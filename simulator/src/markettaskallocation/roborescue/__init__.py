__author__ = 'jack'

from markettaskallocation.common.goal import Goal
from markettaskallocation.common.problem_encoder import PddlGoal, ProblemEncoder
from pddl_parser import PlanDecoder, create_action_map
from . import action


__all__ = ["plan_decoder", "problem_encoder"]


class RoborescuePddlGoal(PddlGoal):
	_SUB_GOAL_MAP = {
		"edge": "cleared"
	}

	@staticmethod
	def is_main_goal(goal: Goal) -> bool:
		return goal.predicate[0] == "rescued"

	@property
	def sub_goal_map(self):
		return self._SUB_GOAL_MAP


problem_encoder = ProblemEncoder(RoborescuePddlGoal, ("police", "medic"))


plan_decoder = PlanDecoder(create_action_map(
	action.Move, action.Unblock, action.Load, action.Unload, action.Rescue, action.Clear
))
