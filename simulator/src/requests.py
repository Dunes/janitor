from heapq import heapify
from logging import getLogger
from action_state import ExecutionState, ActionState
from logger import StyleAdapter
from collections import namedtuple

log = StyleAdapter(getLogger(__name__))


class ChangedAction(namedtuple("ChangedAction", "agents action")):
    pass


class RemovePrestartRequest:

    def __init__(self, deadline):
        raise NotImplementedError()

    def adjust(self, action_queue):
        raise NotImplementedError()


class AdjustToPartialRequest:
    """Adjustment request for current strategy"""
    def __init__(self, deadline):
        self.deadline = deadline

    def adjust(self, action_queue):
        log.debug("AdjustmentRequest.adjust() with queue {}", action_queue.queue)
        queue = []
        adjusted_actions = []
        for action_state in action_queue.queue:
            action = action_state.action
            if action.end_time <= self.deadline:
                queue.append(action_state)
                continue

            old_action = action
            action = action_state.action.as_partial(duration=self.deadline - action.start_time)

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
        action_queue.queue = queue
        return adjusted_actions