from logger import StyleAdapter
from planning_exceptions import ExecutionError
from logging import getLogger
from action import *

log = StyleAdapter(getLogger(__name__))


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
            type(self).apply(self, model)

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
            type(self).apply(self, model)

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
        assert not rm_obj["dirtiness"] < 0
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
            assert not node_state["dirtiness"] < 0
        else:
            duration = node_state["dirtiness"]
            log.info("{} applied partially, but able to fully complete in {}", self, duration)
            type(self).apply(self, model)

        return False
