from priority_queue import PriorityQueue, KeyBasedPriorityQueue

from operator import itemgetter, pos, neg

from unittest import TestCase
from hamcrest import assert_that, is_, equal_to, empty, is_not, instance_of

__author__ = 'jack'


class TestPriorityQueue(TestCase):

    def test_new(self):
        queue = PriorityQueue()
        assert_that(type(queue), equal_to(PriorityQueue))

    def test_append_low_priority(self):
        # given
        queue = PriorityQueue([1])

        # when
        queue.append(2)

        # then
        assert_that(queue.queue, equal_to([1, 2]))

    def test_append_high_priority(self):
        # given
        queue = PriorityQueue([1])

        # when
        queue.append(0)

        # then
        assert_that(queue.queue, equal_to([0, 1]))

    def test_extend(self):
        # given
        queue = PriorityQueue([1])

        # when
        queue.extend([2, 0])

        # then
        assert_that(list(queue.values()), equal_to([0, 1, 2]))

    def test_peek(self):
        # given
        queue = PriorityQueue([1])

        # when
        result = queue.peek()

        # then
        assert_that(result, equal_to(1))
        assert_that(queue.queue, equal_to([1]))

    def test_pop(self):
        # given
        queue = PriorityQueue([1])

        # when
        result = queue.pop()

        # then
        assert_that(result, equal_to(1))
        assert_that(queue.queue, is_(empty()))

    def test_empty(self):
        # given
        empty_ = PriorityQueue()
        not_empty = PriorityQueue([1])

        # then
        assert_that(empty_.empty())
        assert_that(not_empty.empty(), is_not(True))

    def test_values(self):
        # given
        items = [2, 5, 3, 76, 8]
        queue = PriorityQueue(items)

        # then
        assert_that(list(queue.values()), equal_to(sorted(items)))

    def test_clear(self):
        # given
        queue = PriorityQueue([1])

        # when
        queue.clear()

        # then
        assert_that(queue.empty())


class TestKeyBasedPriorityQueue(TestCase):

    def test_new(self):
        queue = PriorityQueue(key=lambda x: x)
        assert_that(queue, is_(instance_of(KeyBasedPriorityQueue)))

    def test_append_low_priority(self):
        # given
        queue = PriorityQueue([("z", 0)], key=itemgetter(1))

        # when
        queue.append(("a", 1))

        # then
        assert_that(list(queue.values()), equal_to([("z", 0), ("a", 1)]))

    def test_append_high_priority(self):
        # given
        queue = PriorityQueue([("z", 0)], key=itemgetter(0))

        # when
        queue.append(("a", 1))

        # then
        assert_that(list(queue.values()), equal_to([("a", 1), ("z", 0)]))

    def test_extend(self):
        # given
        queue = PriorityQueue([("b", 1)], key=itemgetter(1))

        # when
        queue.extend([("a", 2), ("c", 0)])

        # then
        assert_that(list(queue.values()), equal_to([("c", 0), ("b", 1), ("a", 2)]))

    def test_peek(self):
        # given
        queue = PriorityQueue([1], key=pos)

        # when
        result = queue.peek()

        # then
        assert_that(result, equal_to(1))
        assert_that(list(queue.values()), equal_to([1]))

    def test_pop(self):
        # given
        queue = PriorityQueue([1], key=pos)

        # when
        result = queue.pop()

        # then
        assert_that(result, equal_to(1))
        assert_that(list(queue.values()), is_(empty()))

    def test_empty(self):
        # given
        empty_ = PriorityQueue(key=pos)
        not_empty = PriorityQueue([1], key=pos)

        # then
        assert_that(empty_.empty())
        assert_that(not_empty.empty(), is_not(True))

    def test_values(self):
        # given
        items = [2, 5, 3, 76, 8]
        queue = PriorityQueue(items, key=neg)

        # then
        assert_that(list(queue.values()), equal_to(sorted(items, reverse=True)))

    def test_clear(self):
        # given
        queue = PriorityQueue([1], key=pos)

        # when
        queue.clear()

        # then
        assert_that(queue.empty())
