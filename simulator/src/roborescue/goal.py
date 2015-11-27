from collections import namedtuple

__author__ = 'jack'


class Goal(namedtuple("Goal", "predicate deadline")):
    """
    :type predicate: str
    :type deadline: decimal.Decimal
    """
    def __init__(self, predicate, deadline):
        self.predicate = predicate
        self.deadline = deadline
    del __init__


class Task(namedtuple("Task", "goal value")):
    """
    :type goal: Goal
    :type value: decimal.Decimal
    """
    def __init__(self, goal, value):
        self.goal = goal
        self.value = value
    del __init__

    @staticmethod
    def combine(tasks):
        """
        Combines a list of tasks with identical goals into one task
        :param tasks: list[Task]
        :return: Task
        """
        if not tasks:
            raise ValueError("empty sequence")
        if len(tasks) == 1:
            return tasks[0]
        goal = tasks[0].goal
        if not all(t.goal == goal for t in tasks):
            raise ValueError("tried to combine tasks with non-equal goals")
        return Task(goal=goal, value=sum(t.value for t in tasks))


class Bid(namedtuple("Bid", "agent value task requirements computation_time")):
    """
    :type agent: str
    :type value: decimal.Decimal
    :type task: Goal
    :type requirements: list[Task]
    :type computation_time: decimal.Decimal
    """
    def __init__(self, agent, value, task, requirements, computation_time):
        self.agent = agent
        self.value = value
        self.task = task
        self.requirements = requirements
        self.computation_time = computation_time
    del __init__
