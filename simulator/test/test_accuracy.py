"""
Created on 20 Jun 2014

@author: jack
"""
import unittest
from accuracy import quantize
from decimal import Decimal


class AccuracyTest(unittest.TestCase):

    def test_quantize_with_int(self):
        self.assertEqual(Decimal("0"), quantize(0))

    def test_quantize_with_float(self):
        self.assertEqual(Decimal("0"), quantize(0.))

    def test_quantize_rounds_down(self):
        self.assertEqual(Decimal("0"), quantize(0.9))


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()