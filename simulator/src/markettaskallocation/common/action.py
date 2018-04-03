from itertools import chain

from action import Action, Plan, LocalPlan, GetExecutionHeuristic
from accuracy import as_end_time, INSTANTANEOUS_ACTION_DURATION
from markettaskallocation.common.problem_encoder import find_object

__all__ = ["Action", "Plan", "LocalPlan", "GetExecutionHeuristic", "Observe", "EventAction", "Allocate"]


class Observe(Action):
    """
    :type agent: str
    :type node: str
    """
    agent = None
    node = None

    _ordinal = 2

    _format_attrs = ("start_time", "agent", "node")

    _default_at = None, None

    def __init__(self, observation_time, agent, node):
        super(Observe, self).__init__(as_end_time(observation_time), INSTANTANEOUS_ACTION_DURATION)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "node", node)

    def is_applicable(self, model):
        return find_object(self.agent, model["objects"])["at"][1] == self.node

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"

        # check if new knowledge
        changes = []
        # check to see if observe any objects
        for object_id, object_ in chain.from_iterable((v.items() for v in model["objects"].values())):
            unknown = object_.get("unknown")
            if unknown and object_["known"].get("at", self._default_at)[1] == self.node:
                object_["known"].update((k, self._get_actual_value(v)) for k, v in unknown.items())
                if self._check_new_knowledge(unknown, model["assumed-values"]):
                    changes.append(object_id)
                unknown.clear()

        # check to see if observe any edges
        for object_id, object_ in model["graph"]["edges"].items():
            unknown = object_.get("unknown")
            if unknown and self.node in object_id:
                object_["known"].update((k, self._get_actual_value(v)) for k, v in unknown.items())
                if self._check_new_knowledge(unknown, model["assumed-values"]):
                    changes.append(object_id)
                unknown.clear()

        return changes

    @staticmethod
    def _get_actual_value(value):
        actual = value["actual"]  # sometimes produces a key referring to another value in `value'
        return actual if actual not in value else value[actual]

    @staticmethod
    def _check_new_knowledge(unknown_values, assumed_values):
        no_match = object()
        for key, unknown_value in unknown_values.items():
            assumed_value = assumed_values[key]
            if unknown_value["actual"] not in (assumed_value, unknown_value.get(assumed_value, no_match)):
                return True
        return False

    def as_partial(self, **kwargs):
        return None

    def partially_apply(self, model, deadline):
        raise NotImplementedError


class EventAction(Action):
    """
    :type agent: str
    :type events: tuple[tuple[str]]
    """
    agent = None
    events = None

    _format_attrs = ("start_time", "events")

    def __init__(self, time, events):
        super().__init__(as_end_time(time), INSTANTANEOUS_ACTION_DURATION)
        object.__setattr__(self, "agent", "event_executor")
        object.__setattr__(self, "events", events)

    def is_applicable(self, model):
        return True

    def apply(self, model):
        changes = set()
        for e in self.events:
            changes.add(e.apply(model))
        return list(changes)

    def as_partial(self, **kwargs):
        return TypeError("Should not ask event to partially apply")

    def partially_apply(self, model, deadline):
        raise NotImplementedError


class Allocate(Action):
    """
    :type agent: str
    :type goals: list[Goal]
    """
    agent = None
    goals = None

    _format_attrs = ("agent", "start_time")

    def __init__(self, start_time, agent, *, allocation=None, duration=INSTANTANEOUS_ACTION_DURATION):
        super().__init__(start_time, duration)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "allocation", allocation)

    def is_applicable(self, model):
        return True

    def apply(self, model):
        pass

    def as_partial(self, **kwargs):
        return TypeError("Should not ask allocate to partially apply")

    def partially_apply(self, model, deadline):
        raise NotImplementedError