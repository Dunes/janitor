'''
Created on 20 Jun 2014

@author: jack
'''

class Matcher(object):

    def __init__(self, test_case):
        self.test_case = test_case

class MoveMatcher(Matcher):
    def assertEqual(self, expected, actual):
        self.test_case.assertEqual(expected.partial, actual.partial)
        self.test_case.assertEqual(expected.agent, actual.agent)
        self.test_case.assertEqual(expected.start_time, actual.start_time)
        self.test_case.assertEqual(expected.duration, actual.duration)
        self.test_case.assertEqual(expected.start_node, actual.start_node)
        self.test_case.assertEqual(expected.end_node, actual.end_node)

class ModelMatcher(Matcher):

    def with_model(self, model):
        self.model = model
        return self

    def with_agent(self, agent):
        self.agent_name = agent
        return self

    def at(self, at):
        actual = self.model["agents"][self.agent_name]["at"][1]
        self.test_case.assertEqual(actual, at)

    def with_distance(self, distance):
        self.distance = distance
        return self

    def from_(self, from_node):
        self.from_node = from_node
        return self

    def to(self, to_node):
        self.to_node = to_node
        edge = [self.from_node, self.to_node, self.distance]
        self.test_case.assertIn(edge, self.model["graph"]["edges"])

    __call__ = with_model