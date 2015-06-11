from decimal import Decimal
from functools import total_ordering, partial as partial_func
from accuracy import as_end_time, INSTANTANEOUS_ACTION_DURATION
from logger import StyleAdapter
from planning_exceptions import ExecutionError
from logging import getLogger

log = StyleAdapter(getLogger(__name__))


@total_ordering
class Action(object):

    _ordinal = 1

    def __init__(self, start_time, duration, partial=None):
        object.__setattr__(self, "start_time", start_time)
        object.__setattr__(self, "duration", duration)
        if partial is not None:
            object.__setattr__(self, "partial", partial)

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
        if kwargs.get("duration") == 0:
            return None
        obj = self.copy_with(partial=True, **kwargs)
        object.__setattr__(obj, "apply", partial_func(obj.partially_apply, deadline=obj.end_time))
        return obj


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

    _format_attrs = ("start_time", "duration", "agent", "goals", "tils")

    def __init__(self, start_time, duration, agent=None, plan=None, *, goals, tils):
        super(Plan, self).__init__(start_time, duration)
        object.__setattr__(self, "agent", agent if agent else Plan.agent)
        object.__setattr__(self, "plan", plan)
        object.__setattr__(self, "goals", goals)
        object.__setattr__(self, "tils", tils)


class Stalled(Action):

    _format_attrs = ("start_time", "duration", "agent")

    def __init__(self, start_time, duration, agent):
        super(Stalled, self).__init__(start_time, duration)
        object.__setattr__(self, "agent", agent)


class Move(Action):

    _format_attrs = ("start_time", "duration", "agent", "start_node", "end_node", "partial")

    def __init__(self, start_time, duration, agent, start_node, end_node, partial=None):
        super(Move, self).__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "start_node", start_node)
        object.__setattr__(self, "end_node", end_node)

    def is_applicable(self, model):
        return model["agents"][self.agent]["at"][1] == self.start_node

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        model["agents"][self.agent]["at"][1] = self.end_node
        if self.start_node.startswith("temp"):
            del model["nodes"][self.start_node]
            model["graph"]["edges"] = [edge for edge in model["graph"]["edges"] if self.start_node not in edge]
        return False

    def partially_apply(self, model, deadline):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        # create temp node
        continued_partial_move = self.start_node.startswith("temp")
        if continued_partial_move:
            self.modify_temp_node(model, deadline)
        else:
            self.create_temp_node(model, deadline)
        return False

    def modify_temp_node(self, model, deadline):
        temp_node_name = self.start_node

        back_edge, forward_edge = (edge for edge in model["graph"]["edges"] if edge[0] == temp_node_name)

        if forward_edge[1] == self.end_node:
            distance_moved = deadline - self.start_time
        elif back_edge[1] == self.end_node:
            distance_moved = self.start_time - deadline
        else:
            raise ExecutionError("Neither temp node edge links to end_node: edges: {}, action: {}"
                .format([back_edge, forward_edge], self))

        back_edge[2] += distance_moved
        forward_edge[2] -= distance_moved

        assert back_edge[2] > 0
        assert forward_edge[2] > 0

        # create partial action representing move
        action = Move(self.start_time, distance_moved, self.agent, temp_node_name, self.end_node, partial=True)
        return action

    def create_temp_node(self, model, deadline):
        temp_node_name = "-".join(("temp", self.agent, self.start_node, self.end_node))
        if temp_node_name in model["nodes"] or \
                any(edge for edge in model["graph"]["edges"] if edge[0] == temp_node_name):
            log.error("tried to insert {}, but already initialised", temp_node_name)
            assert False
        model["nodes"][temp_node_name] = {"node": True}
        # set up edges -- only allow movement out of node
        distance_moved = deadline - self.start_time
        distance_remaining = self.get_edge_length(model, self.start_node, self.end_node) - distance_moved
        model["graph"]["edges"].append([temp_node_name, self.start_node, distance_moved])
        model["graph"]["edges"].append([temp_node_name, self.end_node, distance_remaining])
        # move agent to temp node
        model["agents"][self.agent]["at"][1] = temp_node_name
        # create partial action representing move
        action = Move(self.start_time, distance_moved, self.agent, self.start_node, temp_node_name, partial=True)
        return action

    def get_edge_length(self, model, start_node, end_node):
        edge_key = [start_node, end_node]
        for edge in model["graph"]["edges"]:
            if edge_key == edge[:2]:
                return edge[-1]
        if model["graph"]["bidirectional"]:
            raise NotImplementedError()
        raise ExecutionError("Could not find {} in {}".format(edge_key, model["graph"]["edges"]))


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


class Clean(Action):

    _format_attrs = ("start_time", "duration", "agent", "room", "partial")

    def __init__(self, start_time, duration, agent, room, partial=None):
        super(Clean, self).__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "room", room)

    def is_applicable(self, model):
        known = model["nodes"][self.room]["known"]
        return (
            model["agents"][self.agent]["at"][1] == self.room
            and known.get("dirty", False)
            and not known.get("extra-dirty", True)
        )

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        rm_obj = model["nodes"][self.room]["known"]
        del rm_obj["dirtiness"]
        del rm_obj["dirty"]
        rm_obj["cleaned"] = True
        return False

    def partially_apply(self, model, deadline):
        assert self.is_applicable(model), "tried to apply action in an invalid state"

        max_duration = deadline - self.start_time
        node_state = model["nodes"][self.room]["known"]
        partial = node_state["dirtiness"] > max_duration

        if partial:
            node_state["dirtiness"] -= max_duration
        else:
            duration = node_state["dirtiness"]
            log.info("{} applied partially, but able to fully complete in {}", self, duration)
            self.apply(model)

        return False


class ExtraClean(Action):

    _format_attrs = ("start_time", "duration", "agent0", "agent1", "room", "partial")

    def __init__(self, start_time, duration, agent0, agent1, room, partial=None):
        super(ExtraClean, self).__init__(start_time, duration, partial)
        object.__setattr__(self, "room", room)
        object.__setattr__(self, "agent0", agent0)
        object.__setattr__(self, "agent1", agent1)

    def is_applicable(self, model):
        known = model["nodes"][self.room]["known"]
        return (
            model["agents"][self.agent0]["at"][1] == self.room
            and model["agents"][self.agent1]["at"][1] == self.room
            and known.get("extra-dirty", False)
            and not known.get("dirty", True)
        )

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        rm_obj = model["nodes"][self.room]["known"]
        del rm_obj["extra-dirty"]
        del rm_obj["dirtiness"]
        rm_obj["cleaned"] = True
        return False

    def partially_apply(self, model, deadline):
        assert self.is_applicable(model), "tried to apply action in an invalid state"

        max_duration = deadline - self.start_time
        node_state = model["nodes"][self.room]["known"]
        partial = node_state["dirtiness"] > max_duration

        if partial:
            node_state["dirtiness"] -= max_duration
        else:
            duration = node_state["dirtiness"]
            log.info("{} applied partially, but able to fully complete in {}", self, duration)
            self.apply(model)

        return False

    def agents(self) -> set:
        return {self.agent0, self.agent1}


class ExtraCleanPart(Action):

    _format_attrs = ("start_time", "duration", "agent", "room", "partial")

    def __init__(self, start_time, duration, agent, room, partial=None):
        super().__init__(start_time, duration, partial)
        object.__setattr__(self, "agent", agent)
        object.__setattr__(self, "room", room)

    def is_applicable(self, model):
        known = model["nodes"][self.room]["known"]
        return (
            model["agents"][self.agent]["at"][1] == self.room
            and not known.get("dirty", True)
            and known.get("extra-dirty", False)
        )

    def apply(self, model):
        assert self.is_applicable(model), "tried to apply action in an invalid state"
        rm_obj = model["nodes"][self.room]["known"]
        rm_obj["dirtiness"] -= self.duration / 2
        if not rm_obj["dirtiness"]:
            del rm_obj["dirtiness"]
            del rm_obj["dirty"]
            rm_obj["cleaned"] = True
        return False

    def partially_apply(self, model, deadline):
        assert self.is_applicable(model), "tried to apply action in an invalid state"

        max_duration = deadline - self.start_time
        node_state = model["nodes"][self.room]["known"]
        partial = node_state["dirtiness"] > max_duration

        if partial:
            node_state["dirtiness"] -= max_duration
        else:
            duration = node_state["dirtiness"]
            log.info("{} applied partially, but able to fully complete in {}", self, duration)
            self.apply(model)

        return False

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
