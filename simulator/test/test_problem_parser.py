'''
Created on 19 Jul 2014

@author: jack
'''
import unittest

from hamcrest import assert_that, equal_to

from decimal import Decimal

import problem_parser
from unittest.mock import patch, mock_open

class TestProblemParser(unittest.TestCase):

    @patch("problem_parser.open", open_mock=mock_open(), create=True)
    def test_encode_with_decimal(self, open_mock):
        # given
        number = "0.100"

        # when
        problem_parser.encode("filename", Decimal(number))

        # then
        mock_file = open_mock().__enter__()
        mock_file.write.assert_called_once_with(number)

    @patch("problem_parser.open", mock_open(read_data="0.100"), create=True)
    def test_decode_with_decimal(self):
        # when
        actual = problem_parser.decode("filename")

        assert_that(actual, equal_to(Decimal("0.100")))

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()