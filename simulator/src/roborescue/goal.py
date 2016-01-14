from collections import namedtuple

__author__ = 'jack'


class Goal(namedtuple("Goal", "predicate deadline")):
    """
    :type predicate: tuple[str]
    :type deadline: decimal.Decimal
    """
    def __init__(self, predicate, deadline):
        super().__init__()
        self.predicate = predicate
        self.deadline = deadline
    del __init__


class Task(namedtuple("Task", "goal value")):
    """
    :type goal: Goal
    :type value: decimal.Decimal
    """
    def __init__(self, goal, value):
        super().__init__()
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


class Bid(namedtuple("Bid", "agent estimated_endtime additional_cost task requirements computation_time")):
    """
    :type agent: str
    :type estimated_endtime: decimal.Decimal
    :type additional_cost: decimal.Decimal
    :type task: Task
    :type requirements: tuple[Task]
    :type computation_time: decimal.Decimal
    """
    def __init__(self, agent, estimated_endtime, additional_cost, task, requirements, computation_time):
        super().__init__()
        self.agent = agent
        self.estimated_endtime = estimated_endtime
        self.additional_cost = additional_cost
        self.task = task
        self.requirements = requirements
        self.computation_time = computation_time
    del __init__
