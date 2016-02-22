from unittest import TestCase
from period import Period, get_contiguous_periods
from action import Action
from decimal import Decimal


class TestPeriod(TestCase):

    def test_overlapping(self):
        # given
        p0 = Period(0, 2)
        p1 = Period(1, 3)

        # then
        self.assertTrue(p0.contiguous(p1))
        self.assertTrue(p1.contiguous(p0))

    def test_abutting(self):
        # given
        p0 = Period(0, 2)
        p2 = Period(2, 4)

        # then
        self.assertTrue(p0.contiguous(p2))
        self.assertTrue(p2.contiguous(p0))

    def test_contained(self):
        # given
        p1 = Period(1, 3)
        p4 = Period(0, 4)

        # then
        self.assertTrue(p1.contiguous(p4))
        self.assertTrue(p4.contiguous(p1))

    def test_not_contiguous(self):
        # given
        p0 = Period(0, 2)
        p3 = Period(3, 5)

        # then
        self.assertFalse(p0.contiguous(p3))
        self.assertFalse(p3.contiguous(p0))

    def test_or(self):
        # given
        p0 = Period(0, 2)
        p1 = Period(1, 3)

        # when
        actual0 = p0 | p1
        actual1 = p1 | p0

        # then
        expected = Period(0, 3)
        self.assertEqual(actual0, expected)
        self.assertEqual(actual1, expected)

    def test_or_error(self):
        # given
        p0 = Period(0, 1)
        p1 = Period(2, 3)

        # then
        with self.assertRaises(ValueError):
            p0 | p1

        # then
        with self.assertRaises(ValueError):
            p1 | p0


class TestGetContiguousPeriods(TestCase):

    def test_groups_contiguous_actions(self):
        # given
        actions = [
            Action(start_time=Decimal(0), duration=Decimal(2)),
            Action(start_time=Decimal(2), duration=Decimal(2))
        ]

        # when
        actual = get_contiguous_periods(actions)

        # then
        self.assertEqual(actual, [Period(start=0, end=4)])

    def test_does_not_group_non_contiguous_actions(self):
        # given
        actions = [
            Action(start_time=Decimal(0), duration=Decimal(2)),
            Action(start_time=Decimal(3), duration=Decimal(2))
        ]

        # when
        actual = get_contiguous_periods(actions)

        # then
        self.assertEqual(actual, [Period(start=0, end=2), Period(start=3, end=5)])

    def test_groups_contiguous_actions_when_not_sorted(self):
        # given
        actions = [
            Action(start_time=Decimal(2), duration=Decimal(2)),
            Action(start_time=Decimal(0), duration=Decimal(2))
        ]

        # when
        actual = get_contiguous_periods(actions)

        # then
        self.assertEqual(actual, [Period(start=0, end=4)])

    def test_doesnt_create_competing_periods(self):
        # given
        actions = [
            Action(start_time=Decimal(0), duration=Decimal(2)),
            Action(start_time=Decimal(10), duration=Decimal(2)),
            Action(start_time=Decimal(2), duration=Decimal(2))
        ]

        # when
        actual = get_contiguous_periods(actions)

        # then
        self.assertEqual(actual, [Period(start=0, end=4), Period(start=10, end=12)])
