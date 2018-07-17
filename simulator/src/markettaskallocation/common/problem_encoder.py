from numbers import Number
from pddl_parser import get_text_file_handle

from markettaskallocation.common.goal import Goal
from abc import ABC, abstractmethod

__author__ = 'jack'
__all__ = ["ProblemEncoder", "PddlGoal", "find_object", "create_predicate"]


def find_object(object_id, objects, return_type=False):
    for object_type, values in objects.items():
        if object_id in values:
            if return_type:
                return object_type, values[object_id]
            else:
                return values[object_id]
    raise KeyError("object {!r} not found".format(object_id))


def create_predicate(predicate_name, value, object_name):
    if value is False:
        return None
    elif value is True:
        return predicate_name, object_name
    elif isinstance(value, Number):
        return "=", (predicate_name, object_name), value
    elif isinstance(value, (list, tuple)):
        if isinstance(value[-1], Number):
            return "=", (predicate_name,) + tuple(v if v is not True else object_name for v in value[:-1]), value[-1]
        else:
            return (predicate_name,) + tuple(v if v is not True else object_name for v in value)
    raise ValueError(
        "known predicate type: name={!r}, value={!r}, object_name={!r}".format(predicate_name, value, object_name)
    )


class PddlGoal(ABC):

    def __init__(self, goal: Goal, preference: bool):
        self.goal = goal
        self.preference = preference
        self.required_symbol = self.as_required_symbol(goal)
        self.pddl_goal = self.as_pddl_goal(goal, self.required_symbol, preference)
        self.preference_name = self.as_preference_name(self.required_symbol)

    @property
    def deadline(self):
        return self.goal.deadline

    @property
    def goal_tuple(self):
        return self.pddl_goal

    @property
    def key(self):
        return self.goal

    @property
    def explicit_deadline(self):
        raise NotImplementedError
        # return not self.is_main_goal(self.goal)

    @property
    def explicit_earliest(self):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def is_main_goal(goal: Goal) -> bool:
        raise NotImplementedError

    @staticmethod
    def as_required_symbol(goal: Goal) -> str:
        return "{}-{}".format("-".join(goal.predicate), goal.deadline)

    @staticmethod
    def as_preference_name(required_symbol: str) -> str:
        return "pref-{}".format(required_symbol)

    def as_pddl_goal(self, goal: Goal, required_symbol: str, preference: bool) -> tuple:
        if preference:
            preference_name = self.as_preference_name(required_symbol)
            return "preference", preference_name, self.as_pddl_predicate(goal, required_symbol)
        else:
            return self.as_pddl_predicate(goal, required_symbol)

    @abstractmethod
    def as_sub_goal(self, goal: Goal, required_symbol: str):
        raise NotImplementedError

    def as_pddl_predicate(self, goal: Goal, required_symbol: str) -> tuple:
        if self.is_main_goal(goal):
            return goal.predicate
        else:
            return self.as_sub_goal(goal, required_symbol)


class ProblemEncoder:

    def __init__(self, pddl_goal_type, agent_type_names):
        self.pddl_goal_type = pddl_goal_type
        self.agent_type_names = agent_type_names

    def encode_problem_to_file(self, filename, model, agent, goals, metric, time, events):
        with get_text_file_handle(filename) as fh:
            self.encode_problem(fh, model, agent, goals, metric, time, events)

    def encode_problem(self, out, model, agent, goals, metric, time, events):
        # convert data
        use_preferences = metric is not None
        goals = self.convert_goals(goals, use_preferences)
        objects = self.collate_object_types(model["objects"], goals)
        object_values = self.collate_objects(model["objects"], agent=agent)

        # encode data to output
        self.encode_preamble(out, "problem-name", model["domain"], use_preferences)
        self.encode_objects(out, objects)
        self.encode_init(
            out, object_values, goals, model["graph"], model["assumed-values"], events, model, time,
            "predicate" in objects)
        self.encode_goal(out, goals)
        if metric is not None:
            self.encode_metric(out, metric, goals)
        # post-amble
        out.write(")")

    @staticmethod
    def encode_preamble(out, problem_name, domain_name, requires_preferences):
        out.write("(define (problem ")
        out.write(problem_name)
        out.write(") (:domain ")
        out.write(domain_name)
        out.write(")")
        if requires_preferences:
            out.write(" (:requirements :preferences)")
        out.write("\n")

    @staticmethod
    def encode_objects(out, objects):
        out.write("(:objects \n")
        for type_, instances in objects.items():
            if instances:
                out.write("    ")
                out.write(" ".join(instances))
                out.write(" - ")
                out.write(type_)
                out.write("\n")
        out.write(")\n")

    def encode_init(self, out, objects, goals, graph, assumed_values, events=None, model=None, time=None,
                    predicates=None):
        out.write("(:init \n")
        out.write("\n    ; objects\n")
        self.encode_init_helper(out, objects, assumed_values)
        if predicates:
            out.write("\n    ; timings\n")
            self.encoding_timings(out, goals)
        out.write("\n    ; events\n")
        self.encode_events(out, events, time, model)
        out.write("\n    ; graph\n")
        self.encode_graph(out, graph, assumed_values)
        out.write(")\n")

    def encoding_timings(self, out, goals):
        """
        :param out: io.StringIO
        :param goals: list[PddlGoal]
        :return: None
        """
        for goal in goals:
            if not goal.explicit_deadline:
                continue
            predicate = "required", goal.required_symbol
            self.encode_predicate(out, predicate, indent="    ")
            if goal.goal.deadline.is_finite():
                self.encode_predicate(out, ("at", goal.goal.deadline, ("not", predicate)), indent="    ")

    def encode_events(self, out, events, time, model):
        if events:
            for event in events:
                for pred in event.get_predicates(time, model):
                    self.encode_predicate(out, pred, indent="    ")

    def encode_init_helper(self, out, items, assumed_values):
        for object_name, object_values in items.items():
            if "known" not in object_values:
                self.encode_init_values(out, object_name, object_values)
            else:
                self.encode_init_values(out, object_name, object_values["known"])
                self.encode_init_values(out, object_name, object_values["unknown"], assumed_values, self.unknown_value_getter)

    def encode_init_values(self, out, object_name, object_values, assumed_values=None, value_getter=(lambda x, _0, _1: x)):
        for value_name, possible_values in object_values.items():
            value = value_getter(possible_values, value_name, assumed_values)
            predicate = create_predicate(value_name, value, object_name)
            if predicate is not None:
                self.encode_predicate(out, predicate, indent="    ")

    @staticmethod
    def unknown_value_getter(possible_values, object_name, assumed_values):
        if "assumed" in possible_values:
            return possible_values["assumed"]
        value = assumed_values[object_name]
        if value in possible_values:
            return possible_values[value]
        else:
            return value

    def encode_predicate(self, out, args, indent=''):
        out.write(indent)
        out.write("(")
        for arg in args:
            if isinstance(arg, (list, tuple)):
                self.encode_predicate(out, arg)
            else:
                out.write(str(arg))
            out.write(" ")
        out.write(") ")
        if indent:
            out.write("\n")

    def encode_function(self, out, args, value):
        out.write("(= ")
        self.encode_predicate(out, args)
        out.write(str(value))
        out.write(") ")

    def encode_graph(self, out, graph, assumed_values):
        self.encode_init_helper(out, graph["edges"], assumed_values)

    def encode_goal(self, out, goals):
        out.write("(:goal (and \n")
        for goal in goals:
            self.encode_predicate(out, goal.goal_tuple, indent="    ")
        out.write("))\n")

    def encode_metric(self, out, metric, goals):
        out.write("(:metric ")
        out.write(metric["type"])
        out.write(" (+ ")
        weights = metric["weights"]
        violations = weights["soft-goal-violations"]
        if "total-time" in weights:
            self.encode_predicate(out, ["*", str(weights["total-time"]), ["total-time"]])
        for goal in goals:
            weight = violations.get(goal.key) or violations[goal.key.predicate[0]]
            self.encode_predicate(out, ["*", weight, ["is-violated", goal.preference_name]])
        out.write(") ) \n")

    def collate_objects(self, objects, agent):
        collated = {}
        if agent == "all":
            for value in objects.values():
                collated.update(value)
        else:
            collated[agent] = find_object(agent, objects)
            for type_, value in objects.items():
                if type_ in self.agent_type_names:
                    continue
                else:
                    collated.update(value)
        return collated

    @staticmethod
    def collate_object_types(objects, goals):
        """
        :param objects:
        :param goals: list[PddlGoal]
        :return:
        """
        objects = {type_: list(objects_) for type_, objects_ in objects.items()}
        predicates = [g.required_symbol for g in goals if g.explicit_deadline]
        if predicates:
            objects["predicate"] = predicates
        return objects

    def convert_goals(self, goals, use_preferences):
        """
        :param goals: list[Goal]
        :param use_preferences: bool
        :return: list[PddlGoal]
        """
        if goals is None:
            raise NotImplementedError
            # goals = model["goal"]

        pddl_goals = []
        for g in goals:
            pddl_goals.append((self.pddl_goal_type(g, use_preferences)))
        return pddl_goals
