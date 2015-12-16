from numbers import Number
from pddl_parser import get_text_file_handle
from copy import deepcopy

__author__ = 'jack'


def encode_problem_to_file(filename, model, agent, goals, metric, time, events):
    with get_text_file_handle(filename) as fh:
        encode_problem(fh, model, agent, goals, metric, time, events)


def encode_problem(out, model, agent, goals, metric, time, events):

    has_metric = metric is not None
    _encode_preamble(out, "problem-name", model["domain"], has_metric)

    objects = {type_: list(objs) for type_, objs in model["objects"].items()}
    _encode_objects(out, objects)

    object_values = _collate_objects(model["objects"], agent=agent)
    _encode_init(out, object_values, model["graph"], model["assumed-values"], events, model, time)

    goals = [g.predicate for g in goals] if goals is not None else model["goal"]
    _encode_goal(out, goals)

    if has_metric:
        if isinstance(goals, dict):
            goals_for_metric = goals["soft-goals"]
        else:
            goals_for_metric = goals
        _encode_metric(out, metric, goals_for_metric)

    # post-amble
    out.write(")")


def _encode_preamble(out, problem_name, domain_name, requires_preferences):
    out.write("(define (problem ")
    out.write(problem_name)
    out.write(") (:domain ")
    out.write(domain_name)
    out.write(")")
    if requires_preferences:
        out.write(" (:requirements :preferences)")
    out.write("\n")


def _encode_objects(out, objects):
    out.write("(:objects ")
    for type_, instances in objects.items():
        if instances:
            out.write(" ".join(instances))
            out.write(" - ")
            out.write(type_)
            out.write(" ")
    out.write(")\n")


def _encode_init(out, objects, graph, assumed_values, events=None, model=None, time=None):
    out.write("(:init ")
    _encode_init_helper(out, objects, assumed_values)
    _encode_events(out, events, time, model)
    _encode_graph(out, graph, assumed_values)
    out.write(") ")


def _encode_events(out, events, time, model):
    if events:
        for event in events:
            for pred in event.get_predicates(time, model):
                _encode_predicate(out, pred)


def _encode_init_helper(out, items, assumed_values):
    for object_name, object_values in items.items():
        if "known" not in object_values:
            _encode_init_values(out, object_name, object_values)
        else:
            _encode_init_values(out, object_name, object_values["known"])
            _encode_init_values(out, object_name, object_values["unknown"], assumed_values, unknown_value_getter)


def _encode_init_values(out, object_name, object_values, assumed_values=None, value_getter=(lambda x, _0, _1: x)):
    for value_name, possible_values in object_values.items():
        value = value_getter(possible_values, value_name, assumed_values)
        predicate = create_predicate(value_name, value, object_name)
        if predicate is not None:
            _encode_predicate(out, predicate)


def unknown_value_getter(possible_values, object_name, assumed_values):
    if "assumed" in possible_values:
        return possible_values["assumed"]
    value = assumed_values[object_name]
    if value in possible_values:
        return possible_values[value]
    else:
        return value


def _encode_predicate(out, args):
    out.write("(")
    for arg in args:
        if isinstance(arg, (list, tuple)):
            _encode_predicate(out, arg)
        else:
            out.write(str(arg))
        out.write(" ")
    out.write(") ")


def _encode_function(out, args, value):
    out.write("(= ")
    _encode_predicate(out, args)
    out.write(str(value))
    out.write(") ")


def _encode_graph(out, graph, assumed_values):
    _encode_init_helper(out, graph["edges"], assumed_values)


def _encode_goal(out, goals):
    out.write("(:goal (and ")
    if isinstance(goals, list):
        for goal in goals:
            _encode_predicate(out, goal)
    else:  # is dict
        for goal in goals.get("hard-goals", ()):
            _encode_predicate(out, goal)
        for soft_goal in goals.get("soft-goals", ()):
            _encode_predicate(out, ["preference", "-".join(soft_goal), soft_goal])
    out.write("))\n")


def _encode_metric(out, metric, goals):
    out.write("(:metric ")
    out.write(metric["type"])
    out.write(" (+ ")
    weights = metric["weights"]
    violations = weights["soft-goal-violations"]
    if "total-time" in weights:
        _encode_predicate(out, ["*", str(weights["total-time"]), ["total-time"]])
    for goal in goals:
        weight = violations.get(tuple(goal)) or violations[goal[0]]
        _encode_predicate(out, ["*", weight, ["is-violated", "-".join(goal)]])
    out.write(") ) \n")


def _collate_objects(objects, agent):
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
