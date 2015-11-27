from decimal import Decimal
from functools import total_ordering, partial as partial_func
from accuracy import as_end_time, INSTANTANEOUS_ACTION_DURATION

__all__ = ["Action", "Plan", "LocalPlan", "Stalled", "Observe", "GetExecutionHeuristic"]


@total_ordering
class Action(object):
    """
    :type start_time: Decimal
    :type duration: Decimal
    """
    start_time = None
    duration = None

    _ordinal = 1

    def __init__(self, start_time, duration, partial=None):
        object.__setattr__(self, "start_time", start_time)
        object.__setattr__(self, "duration", duration)
        if partial is not None:
            object.__setattr__(self, "partial", partial)
            self.start_time = start_time

    def __setattr__(self, key, value):
        raise TypeError("Action objects are immutable")

    def __delattr__(self, item):
        raise TypeError("Action objects are immutable")

    def __eq__(self, other):
        return type(self) is type(other) and self.__dict__ == other.__dict__

    def __lt__(self, other):
        if isinstance(other, Action):
            return self._ordinal < other._ordinal
        raise TypeError("Expected instance of Action, got: {}".format(type(other)))

    @property
    def end_time(self):
        return as_end_time(self.start_time + self.duration)

    def is_applicable(self, model):
        raise NotImplementedError()

    def apply(self, model):
        raise NotImplementedError()

    def partially_apply(self, model, deadline):
        raise NotImplementedError("{} cannot be partially applied".format(self))

    def __str__(self):
        return self._format(False)

    def __repr__(self):
        return self._format(True)

    @staticmethod
    def _format_pair(key, value, _repr):
        if not _repr and type(value) is Decimal:
            return "{}={!s}".format(key, value)
        else:
            return "{}={!r}".format(key, value)

    _format_attrs = ("start_time", "duration", "partial")

    def _format(self, _repr):
        return "{}({})".format(self.__class__.__name__,
            ", ".join(self._format_pair(attr, getattr(self, attr), _repr) for attr in
                self._format_attrs if hasattr(self, attr))
        )

    def agents(self) -> set:
        return {self.agent}

    def copy_with(self, **kwargs):
        assert "apply" not in vars(self)
        attributes = self.__dict__.copy()
        attributes.update(kwargs)
        return self.__class__(**attributes)

    def as_partial(self, end_time=None, **kwargs):
        if end_time is not None:
            assert "duration" not in kwargs
            assert end_time >= self.start_time
            kwargs["duration"] = end_time - self.start_time

        if kwargs.get("duration") == 0:
            return None

        obj = self.copy_with(partial=True, **kwargs)
        object.__setattr__(obj, "apply", partial_func(obj.partially_apply, deadline=obj.end_time))
        return obj

    def is_effected_by_change(self, id_):
        return False


class Plan(Action):

    _ordinal = 3

    _format_attrs = ("start_time", "duration", "agent")

    agent = "planner"

    def __init__(self, start_time, duration, agent=None, plan=None):
        super(Plan, self).__init__(start_time, duration)
        object.__setattr__(self, "agent", agent if agent else Plan.agent)
        object.__setattr__(self, "plan", plan)

    def is_applicable(self, model):
        return True

    def apply(self, model):
        return self.plan


class LocalPlan(Plan):

    _format_attrs = ("start_time", "duration", "agent", "goals", "events")

    def __init__(self, start_time, duration, agent=None, plan=None, *, goals, local_events):
        super(Plan, self).__init__(start_time, duration)
        object.__setattr__(self, "agent", agent if agent else Plan.agent)
        object.__setattr__(self, "plan", plan)
        object.__setattr__(self, "goals", goals)
        object.__setattr__(self, "local_events", local_events)


class Stalled(Action):

    _format_attrs = ("start_time", "duration", "agent")

    def __init__(self, start_time, duration, agent):
        super(Stalled, self).__init__(start_time, duration)
        object.__setattr__(self, "agent", agent)


class Observe(Action):

    _ordinal = 2

    _format_attrs = ("start_time", "agent", "node")

    def __init__(self, observation_time, agent, node):
        super(Observe, self).__init__(as_end_time(observation_time), INSTANTANEOUS_ACTION_DURATION)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "node", node)

    def is_applicable(self, model):
        return model["agents"][self.agent]["at"][1] == self.node

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        # check if new knowledge
        rm_obj = model["nodes"][self.node]
        unknown = rm_obj.get("unknown")

        if unknown:
            rm_obj["known"].update((k, self._get_actual_value(v)) for k, v in unknown.items())
            result = self._check_new_knowledge(unknown, model["assumed-values"])
            unknown.clear()
            return result

        return False

    @staticmethod
    def _get_actual_value(value):
        actual = value["actual"]  # sometimes procduces a key refering to another value in `value'
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


class GetExecutionHeuristic(Action):

    _format_attrs = ("start_time", "duration", "agent")

    def __init__(self, start_time, duration=Decimal(0), agent=None, plan=None):
        super(GetExecutionHeuristic, self).__init__(start_time, duration=duration)
        object.__setattr__(self, "agent", agent if agent else Plan.agent)
        object.__setattr__(self, "plan", plan)

    def is_applicable(self, model):
        return True

    def apply(self, model):
        return self.plan
