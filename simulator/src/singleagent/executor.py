__author__ = 'jack'

from collections import Iterable
from logging import getLogger
from operator import attrgetter
from decimal import Decimal
from accuracy import quantize, as_end_time, as_start_time
from singleagent.agent import Agent
from action import Plan, Observe, Move, GetExecutionHeuristic
from action_state import ActionState, ExecutionState
from copy import copy
from logger import StyleAdapter
from priority_queue import MultiActionQueue
from requests import AdjustToPartialRequest, RemoveActionsWithStateRequest, ActionRequest, MultiRequest
from planning_exceptions import ExecutionError
from itertools import count
from weakref import WeakValueDictionary
from abc import abstractmethod, ABCMeta


log = StyleAdapter(getLogger(__name__))


class Executor(metaclass=ABCMeta):

    ID_COUNTER = count()
    EXECUTORS = WeakValueDictionary()

    def __init__(self, *, deadline):
        self.executing = None
        self._deadline = deadline
        self.id = next(self.ID_COUNTER)
        self.EXECUTORS[self.id] = self

    @abstractmethod
    def copy(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def deadline(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def has_goals(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def next_action(self):
        raise NotImplementedError

    @abstractmethod
    def notify_action_starting(self, action_state: ActionState, model):
        raise NotImplementedError

    @abstractmethod
    def notify_action_finishing(self, action_state: ActionState, model):
        raise NotImplementedError


class AgentExecutor(Executor):

    def __init__(self, *, plan=None, deadline=Decimal("Infinity"), planner_id):
        super().__init__(deadline=deadline)
        self.plan = plan or []
        self.planner_id = planner_id

    def copy(self):
        raise NotImplementedError
        log.debug("Executor.copy()")

    @property
    def deadline(self):
        return self._deadline

    @deadline.setter
    def deadline(self, deadline):
        self._deadline = deadline
        if self.executing:
            new_action = self.executing.action.as_partial(deadline)
            if not new_action:
                raise ExecutionError("executing action does not want to partially complete")
            self.executing = ActionState(new_action, deadline, ExecutionState.executing)
        new_plan = []
        for a in self.plan:
            if a.end_time <= deadline:
                new_plan.append(a)
            else:
                partial_action = a.as_partial(deadline)
                if partial_action:
                    new_plan.append(partial_action)
                break
        self.plan = new_plan

    @property
    def has_goals(self):
        return bool(self.plan or self.executing)

    @property
    def next_action(self):
        if self.executing:
            return self.executing
        return ActionState(self.plan[0])

    def notify_action_starting(self, action_state: ActionState, model):
        log.debug("Executor.notify_action_starting() action_state={}", action_state)
        assert not self.executing
        self.executing = action_state.start()

    def notify_action_finishing(self, action_state: ActionState, model):
        assert self.executing is action_state
        self.executing = None
        action_state = action_state.finish()
        action_state.action.apply(model)


class CentralPlannerExecutor(Executor):

    planner = Planner()

    def __init__(self, *, executor_ids, agent_names, deadline=Decimal("Infinity")):
        super().__init__(deadline=deadline)
        self.valid_plan = False
        self.planning_duration = 10
        self.executor_ids = executor_ids
        assert len(executor_ids) == len(agent_names)
        self.agent_executor_map = {name: id_ for name, id_ in zip(agent_names, executor_ids)}

    def copy(self):
        raise NotImplementedError

    @property
    def deadline(self):
        return self._deadline

    @deadline.setter
    def deadline(self, deadline):
        self._deadline = deadline
        if self.executing:
            raise ExecutionError("Wasn't expecting to be told deadline is changing when already planning")

    @property
    def has_goals(self):
        return not self.valid_plan

    def next_action(self, time):
        assert not self.valid_plan
        if self.executing:
            return self.executing
        return ActionState(Plan(time, self.planning_duration))

    def notify_action_starting(self, action_state: ActionState, model):
        assert not self.executing
        self.executing = action_state.start()

    def notify_action_finishing(self, action_state: ActionState, model):
        assert self.executing is action_state
        self.executing = None
        action_state = action_state.finish()
        action_state.action.apply(model)
