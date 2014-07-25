"""
Created on 22 Jul 2014

@author: jack
"""

import unittest


def load_tests(loader, tests, pattern):
    return loader.discover('.')

if __name__ == '__main__':
    unittest.main()