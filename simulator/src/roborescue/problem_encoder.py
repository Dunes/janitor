from numbers import Number
from pddl_parser import get_text_file_handle

from .goal import Goal

__author__ = 'jack'
__all__ = ["encode_problem", "encode_problem_to_file"]


class PddlGoal:

    def __init__(self, goal: Goal, preference: bool, explicit_deadline: bool):
        self.goal = goal
        self.preference = preference
        self.explicit_deadline = explicit_deadline

    @property
    def deadline(self):
        return self.goal.deadline

    @property
    def goal_tuple(self):
        if self.preference:
            if self.goal.predicate[0] == "rescued":
                return "preference", self.preference_name, self.goal.predicate
            else:
                return "preference", self.preference_name, (self.goal.predicate + (self.predicate_name,))
        else:
            if self.goal.predicate[0] == "rescued":
                return self.goal.predicate
            else:
                return self.goal.predicate + (self.predicate_name,)

    @property
    def preference_name(self):
        return "pref-{}".format(self.predicate_name)

    @property
    def predicate_name(self):
        return "-".join(self.goal.predicate + (str(self.goal.deadline),))


def encode_problem_to_file(filename, model, agent, goals, metric, time, events):
    with get_text_file_handle(filename) as fh:
        encode_problem(fh, model, agent, goals, metric, time, events)


def encode_problem(out, model, agent, goals, metric, time, events):
    # convert data
    use_preferences = metric is not None
    goals = convert_goals(goals, use_preferences)
    objects = collate_object_types(model["objects"], goals)
    object_values = collate_objects(model["objects"], agent=agent)

    # encode data to output
    encode_preamble(out, "problem-name", model["domain"], use_preferences)
    encode_objects(out, objects)
    encode_init(out, object_values, goals, model["graph"], model["assumed-values"], events, model, time,
                use_preferences)
    encode_goal(out, goals)
    if metric is not None:
        encode_metric(out, metric, goals)
    # post-amble
    out.write(")")


def encode_preamble(out, problem_name, domain_name, requires_preferences):
    out.write("(define (problem ")
    out.write(problem_name)
    out.write(") (:domain ")
    out.write(domain_name)
    out.write(")")
    if requires_preferences:
        out.write(" (:requirements :preferences)")
    out.write("\n")


def encode_objects(out, objects):
    out.write("(:objects ")
    for type_, instances in objects.items():
        if instances:
            out.write(" ".join(instances))
            out.write(" - ")
            out.write(type_)
            out.write(" ")
    out.write(")\n")


def encode_init(out, objects, goals, graph, assumed_values, events=None, model=None, time=None,
                use_preferences=None):
    out.write("(:init ")
    encode_init_helper(out, objects, assumed_values)
    if not use_preferences:
        encode_deadlines(out, goals)
    encode_events(out, events, time, model)
    encode_graph(out, graph, assumed_values)
    out.write(") ")


def encode_deadlines(out, goals):
    """
    :param out: io.StringIO
    :param goals: list[PddlGoal]
    :return: None
    """
    for goal in goals:
        if not goal.explicit_deadline:
            continue
        predicate = "required", goal.predicate_name
        encode_predicate(out, predicate)
        if goal.goal.deadline.is_finite():
            encode_predicate(out, ("at", goal.goal.deadline, ("not", predicate)))


def encode_events(out, events, time, model):
    if events:
        for event in events:
            for pred in event.get_predicates(time, model):
                encode_predicate(out, pred)


def encode_init_helper(out, items, assumed_values):
    for object_name, object_values in items.items():
        if "known" not in object_values:
            encode_init_values(out, object_name, object_values)
        else:
            encode_init_values(out, object_name, object_values["known"])
            encode_init_values(out, object_name, object_values["unknown"], assumed_values, unknown_value_getter)


def encode_init_values(out, object_name, object_values, assumed_values=None, value_getter=(lambda x, _0, _1: x)):
    for value_name, possible_values in object_values.items():
        value = value_getter(possible_values, value_name, assumed_values)
        predicate = create_predicate(value_name, value, object_name)
        if predicate is not None:
            encode_predicate(out, predicate)


def unknown_value_getter(possible_values, object_name, assumed_values):
    if "assumed" in possible_values:
        return possible_values["assumed"]
    value = assumed_values[object_name]
    if value in possible_values:
        return possible_values[value]
    else:
        return value


def encode_predicate(out, args):
    out.write("(")
    for arg in args:
        if isinstance(arg, (list, tuple)):
            encode_predicate(out, arg)
        else:
            out.write(str(arg))
        out.write(" ")
    out.write(") ")


def encode_function(out, args, value):
    out.write("(= ")
    encode_predicate(out, args)
    out.write(str(value))
    out.write(") ")


def encode_graph(out, graph, assumed_values):
    encode_init_helper(out, graph["edges"], assumed_values)


def encode_goal(out, goals):
    out.write("(:goal (and ")
    for goal in goals:
        encode_predicate(out, goal.goal_tuple)
    out.write("))\n")


def encode_metric(out, metric, goals):
    out.write("(:metric ")
    out.write(metric["type"])
    out.write(" (+ ")
    weights = metric["weights"]
    violations = weights["soft-goal-violations"]
    if "total-time" in weights:
        encode_predicate(out, ["*", str(weights["total-time"]), ["total-time"]])
    for goal in goals:
        weight = violations.get(tuple(goal)) or violations[goal[0]]
        encode_predicate(out, ["*", weight, ["is-violated", "-".join(goal)]])
    out.write(") ) \n")


def collate_objects(objects, agent):
    collated = {}
    if agent == "all":
        for value in objects.values():
            collated.update(value)
    else:
        collated[agent] = find_object(agent, objects)
        for type_, value in objects.items():
            if type_ in ("medic", "police"):
                continue
            else:
                collated.update(value)
    return collated


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
    raise ValueError("known predicate type: name={!r}, value={!r}, object_name={!r}"
        .format(predicate_name, value, object_name))


def collate_object_types(objects, goals):
    """
    :param objects:
    :param goals: list[PddlGoal]
    :return:
    """
    objects = {type_: list(objects_) for type_, objects_ in objects.items()}
    predicates = [g.predicate_name for g in goals if g.explicit_deadline]
    if predicates:
        objects["predicate"] = predicates
    return objects


def convert_goals(goals, use_preferences):
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
        explicit_deadline = g.predicate[0] != "rescued"
        if g.predicate[0] == "edge":
            g = Goal(predicate=("cleared",) + g.predicate[1:], deadline=g.deadline)
        new_goal = PddlGoal(g, use_preferences, explicit_deadline)
        pddl_goals.append(new_goal)
    return pddl_goals
