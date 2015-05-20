__author__ = 'jack'

import unittest
from unittest.mock import MagicMock, Mock, patch, call

from hamcrest import assert_that, contains, is_not, empty, is_, has_length, has_item, equal_to

from singleagent.executor import Executor

class TestDeadline(unittest.TestCase):

    def test_set(self):
        executor = Executor(0, agents=("agent",))
        executor.deadline = 10
        assert executor.deadline == 10
        assert executor._deadline == 10

