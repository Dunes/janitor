'''
Created on 3 Jul 2014

@author: jack
'''
import unittest

from functools import partial

from action import Action, Move, Clean, ExtraClean, Observe, Plan
from util.matcher import ActionMatcher, MoveMatcher, CleanMatcher, ExtraCleanMatcher, ObserveMatcher, PlanMatcher


class BaseTestCase(unittest.TestCase):

    def setUp(self):
        self.addTypeEqualityFunc(Action, partial(ActionMatcher.assertEqual, self))
        self.addTypeEqualityFunc(Move, partial(MoveMatcher.assertEqual, self))
        self.addTypeEqualityFunc(Clean, partial(CleanMatcher.assertEqual, self))
        self.addTypeEqualityFunc(ExtraClean, partial(ExtraCleanMatcher.assertEqual, self))
        self.addTypeEqualityFunc(Observe, partial(ObserveMatcher.assertEqual, self))
        self.addTypeEqualityFunc(Plan, partial(PlanMatcher.assertEqual, self))
