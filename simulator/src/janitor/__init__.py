__author__ = 'jack'

from pddl_parser import PlanDecoder, create_action_map
from . import action

plan_decoder = PlanDecoder(create_action_map(action.Move, action.Clean, action.ExtraClean, action.ExtraCleanPart))
