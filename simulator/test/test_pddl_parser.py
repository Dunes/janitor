"""
Created on 22 Jun 2014

@author: jack
"""
# test framework imports
import unittest
from unittest.mock import patch, Mock
from hamcrest import assert_that, equal_to
from util.functools import as_list

# module under test
import pddl_parser

# imports from std library for tests
import itertools
from textwrap import dedent
from io import StringIO

# imports from project for tests
from planning_exceptions import IncompletePlanException
from pddl_parser import decode_plan
from action import Move, Clean
from accuracy import quantize


class PddlDecodeTest(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @patch("pddl_parser.dropwhile", new=as_list(itertools.dropwhile))
    @patch("pddl_parser.decode_plan")
    def test_decode_plan_from_optic(self, decode_plan):
        # given
        report_incomplete_plan = Mock()
        data_input = dedent("""
            ; No metric specified - using make-span

            ; Plan found with metric 52.007
            ; States evaluated so far: 51
            ; States pruned based on pre-heuristic cost lower bound: 0
            ; Time 0.07
            0.000: (move agent2 n1 rm1)  [1.000]
            0.000: (move agent1 n1 n2)  [10.000]
            1.000: (clean agent2 rm1)  [5.000]
            6.000: (move agent2 rm1 n1)  [1.000]
            7.001: (move agent2 n1 n2)  [10.000]""").split("\n")

        expected_data = dedent("""
            0.000: (move agent2 n1 rm1)  [1.000]
            0.000: (move agent1 n1 n2)  [10.000]
            1.000: (clean agent2 rm1)  [5.000]
            6.000: (move agent2 rm1 n1)  [1.000]
            7.001: (move agent2 n1 n2)  [10.000]""").split("\n")[1:]

        # when
        pddl_parser.decode_plan_from_optic(data_input, report_incomplete_plan)

        # then
        decode_plan.assert_called_once_with(expected_data, report_incomplete_plan)

    def test_decode_plan_with_empty_input(self):
        data_input = []
        report_incomplete_plan = True

        with self.assertRaises(IncompletePlanException):
            list(pddl_parser.decode_plan(data_input, report_incomplete_plan))

    def test_decode_plan_with_incomplete_input(self):
        # given
        data_input = StringIO(dedent("""
            0.000: (move agent2 n1 rm1)  [1.000]
            0.000: (move agent1 n1 n2)  [10.000]
            1.000: (clean agent2 rm1)  [5.000]
            6.000: (move agent2 rm1 n1)  [1.000]
            7.001: (move agent2 n1 n2)  [10.000]
            """).strip())
        report_incomplete_plan = True

        # then
        with self.assertRaises(IncompletePlanException):
            # when
            list(decode_plan(data_input, report_incomplete_plan))

    def test_decode_plan_with_complete_input(self):
        # given
        data_input = StringIO(dedent("""
            0.000: (move agent1 n1 n2)  [10.000]
            1.000: (clean agent2 rm1)  [5.000]
            """).lstrip())
        report_incomplete_plan = False
        expected_move = Move(quantize(0), quantize(10), "agent1", "n1", "n2")
        expected_clean = Clean(quantize(1), quantize(5), "agent2", "rm1")

        # when
        actual = list(decode_plan(data_input, report_incomplete_plan))

        # then
        self.assertEquals(2, len(actual))
        actual_move, actual_clean = actual
        assert_that(actual_move, equal_to(expected_move))
        assert_that(actual_clean, equal_to(expected_clean))


if __name__ == "__main__":
    unittest.main()