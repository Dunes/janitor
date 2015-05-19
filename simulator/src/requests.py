from heapq import heapify
from itertools import chain
from abc import abstractmethod, ABCMeta
from logging import getLogger
from action import Plan
from action_state import ExecutionState, ActionState
from logger import StyleAdapter
from collections import namedtuple
from priority_queue import MultiActionStateQueue
from accuracy import as_start_time

log = StyleAdapter(getLogger(__name__))


class ChangedAction(namedtuple("ChangedAction", "agents action")):
    pass


class Request(metaclass=ABCMeta):

    @abstractmethod
    def adjust(self, action_queue):
        raise NotImplementedError()

    def __add__(self, other):
        if self and other:
            return MultiRequest(chain(self._as_iter(self), self._as_iter(other)))
        elif other:
            return MultiRequest(self._as_iter(other))
        else:
            return self

    def __radd__(self, other):
        if self and other:
            return MultiRequest(chain(self._as_iter(other), self._as_iter(self)))
        elif other:
            return MultiRequest(self._as_iter(other))
        else:
            return self

    @staticmethod
    def _as_iter(request):
        try:
            return iter(request)
        except TypeError:
            return request,


class ActionRequest(Request):

    def __init__(self, actions):
        self.actions = actions

    def adjust(self, action_queue):
        action_queue.put(ActionState(action) for action in self.actions)
        return True

    def __bool__(self):
        return bool(self.actions)


class MultiRequest(Request, tuple):

    def adjust(self, action_queue):
        result = None
        for sub_request in self:
            result = sub_request.adjust(action_queue) or result
        return result


class RemoveActionsWithStateRequest(Request):

    def __init__(self, deadline, *states):
        self.states = states
        self.deadline = deadline

    def adjust(self, action_queue):
        log.debug("RemoveActionsWithStateRequest.adjust() with queue {}", action_queue.queue)
        queue = []
        adjusted_actions = []
        for action_state in action_queue.queue:
            action = action_state.action
            if action.end_time <= self.deadline or action_state.state not in self.states:
                queue.append(action_state)
            else:
                adjusted_actions.append(ChangedAction(agents=action.agents(), action=None))
        heapify(queue)
        action_queue.queue = queue
        return adjusted_actions


class AdjustToPartialRequest(Request):
    """Adjustment request for current strategy"""
    def __init__(self, deadline):
        self.deadline = deadline

    def adjust(self, action_queue: MultiActionStateQueue):
        log.debug("AdjustmentRequest.adjust() with queue {}", action_queue.queue)
        queue = []
        adjusted_actions = []
        for action_state in action_queue.values():
            action = action_state.action
            if action.end_time <= self.deadline or type(action) is Plan:
                queue.append(action_state)
                continue

            old_action = action
            action = action_state.action.as_partial(duration=as_start_time(self.deadline - action.start_time))

            if action and not action.duration > 0:
                assert action.duration > 0

            adjusted_actions.append(ChangedAction(agents=old_action.agents(), action=action))
            if action:
                if action_state.state == ExecutionState.executing:
                    action_state = ActionState(action)
                    action_state.start()
                else:
                    action_state = ActionState(action)
                queue.append(action_state)
        heapify(queue)
        action_queue.clear()
        action_queue.put(queue)
        return adjusted_actions


class AssertAgentsFinishingNowRequest(Request):

    def __init__(self, deadline):
        self.deadline = deadline

    def adjust(self, action_queue):
        for action_state in action_queue.queue:
            assert action_state.action.end_time == self.deadline
        return ()