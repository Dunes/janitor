#! /usr/bin/env python

import argparse
import re
from collections import namedtuple
from copy import deepcopy
from itertools import chain
from random import randint as rand, choice, sample

from problem_parser import encode
from roborescue.action import Observe
from accuracy import quantize
from decimal import Decimal


class Point(namedtuple("Point", "x y")):
    pass


class MinMax(namedtuple("MinMax", "min max")):
    pass


class TupleAction(argparse.Action):
    def __init__(self, maintype, subtype, **kwargs):
        super(TupleAction, self).__init__(**kwargs)
        self.maintype = maintype
        self.subtype = subtype

    def create(self, values):
        if isinstance(values, str):
            v = self.create_item(values)
        else:
            v = tuple(self.create_item(i) for i in values)
        return v

    def create_item(self, values):
        return self.maintype(*(self.subtype(i) for i in values.split(",")))


class MinMaxAction(TupleAction):
    def __init__(self, **kwargs):
        super(MinMaxAction, self).__init__(MinMax, int, **kwargs)

    def __call__(self, parser_, namespace, values, option_string=None):
        v = self.create(values)
        setattr(namespace, self.dest, v)


class PointAction(TupleAction):
    def __init__(self, **kwargs):
        super(PointAction, self).__init__(Point, int, **kwargs)

    def __call__(self, parser_, namespace, values, option_string=None):
        v = self.create(values)
        setattr(namespace, self.dest, v)


def parser():
    p = argparse.ArgumentParser(description="Creates problems from parameters")
    p.add_argument("--output", "-o", required=True)
    p.add_argument("--size", "-s", required=True, action=PointAction, help="the size of the map grid, specified as x,y")
    p.add_argument("--buriedness", "-bu", required=True, action=MinMaxAction)
    p.add_argument("--blockedness", "-bo", required=True, action=MinMaxAction)
    p.add_argument("--blocked-percentage", "-bo%", required=True, type=Decimal)
    p.add_argument("--civilians", "-c", required=True, type=int)
    p.add_argument("--edge-length", "-el", default=100, type=int)

    p.add_argument("--medics", "-m", required=True, type=int)
    p.add_argument("--police", "-p", required=True, type=int)
    p.add_argument("--hospitals", "-ho", nargs="+", action=PointAction)

    p.add_argument("--problem-name", "-pn", required=True)
    p.add_argument("--domain", "-dn", required=True)
    return p


def create_problem(output, size, buriedness, blockedness, blocked_percentage, civilians, edge_length,
                   medics, police, hospitals, problem_name, domain):

    problem = {
        "problem": problem_name,
        "domain": domain,
        "assumed-values": {
            "edge": True,
            "blocked-edge": False,
            "blockedness": "max",
            "buriedness": "max"
        },
        "objects": create_objects(civilians, buriedness, medics, police, size, hospitals),
        "graph": create_graph(size, hospitals, edge_length, blockedness, blocked_percentage),
        "events": [],
        "goal": {"soft-goals": [["rescued", "civ{}".format(i)] for i in range(civilians)]},
        "metric": {
            "type": "minimize",
            "weights": {
                "total-time": 1,
                "soft-goal-violations": {"rescued": 1000000}
            }
        },
    }

    # start problem such that agents have observed starting location
    for agent_name, agent in chain(problem["objects"]["medic"].items(), problem["objects"]["police"].items()):
        node = agent["at"][1]
        Observe(quantize(0), agent_name, node).apply(problem)

    encode(output, problem, sort_keys=True, indent=4)


def create_objects(civilians, buriedness, medics, police, size, hospitals):
    hospital_names = create_hospital_names(hospitals)
    hospital_objects = {name: {} for name in hospital_names}
    building_names = create_building_names(size, hospitals)
    building_objects = {name: {} for name in building_names}
    police_objects = {"police{}".format(i):
                          {
                              "at": [True, choice(hospital_names)],
                              "available": True
                          }
                      for i in range(police)}
    medic_objects = {"medic{}".format(i):
                         {
                             "at": [True, choice(hospital_names)],
                             "available": True,
                             "empty": True
                         }
                     for i in range(medics)}
    civilian_objects = {"civ{}".format(i):
                            {
                                "known": {"at": [True, choice(building_names)], "alive": True, "buried": True},
                                "unknown": {"buriedness": {
                                    "max": buriedness.max,
                                    "min": buriedness.min,
                                    "actual": rand(buriedness.min, buriedness.max)
                                }}
                            }
                        for i in range(civilians)}

    return {
        "medic": medic_objects,
        "police": police_objects,
        "civilian": civilian_objects,
        "hospital": hospital_objects,
        "building": building_objects
    }


def create_graph(size, hospitals, edge_length, blockedness, blocked_percentage):

    hospital_names = create_hospital_names(hospitals)
    building_names = create_building_names(size, hospitals)
    grid = [[None] * size.y for _ in range(size.x)]
    for name in hospital_names + building_names:
        x, y = (int(s) for s in re.findall("[0-9]+", name))
        grid[x][y] = name

    edges = {}
    default_edge = {"known": {"distance": edge_length}, "unknown": {}}
    for x, column in enumerate(grid):
        for y, node in enumerate(column):
            if x - 1 >= 0:
                id_ = "{} {}".format(node, grid[x - 1][y])
                edges[id_] = deepcopy(default_edge)
            if x + 1 < size.x:
                id_ = "{} {}".format(node, grid[x + 1][y])
                edges[id_] = deepcopy(default_edge)
            if y - 1 >= 0:
                id_ = "{} {}".format(node, grid[x][y - 1])
                edges[id_] = deepcopy(default_edge)
            if y + 1 < size.y:
                id_ = "{} {}".format(node, grid[x][y + 1])
                edges[id_] = deepcopy(default_edge)

    unique_edges = set(tuple(sorted(edge_id.split())) for edge_id in edges)
    blocked_edges = sample(list(unique_edges), int(round(len(unique_edges) * blocked_percentage)))
    unblocked_edges = list(unique_edges.difference(blocked_edges))
    for edge_pair in blocked_edges:
        unknown_edge_data = {
            "edge": {"actual": False},
            "blocked-edge": {"actual": True},
            "blockedness": {
                "max": blockedness.max,
                "min": blockedness.min,
                "actual": rand(blockedness.min, blockedness.max)
            }
        }
        edges[" ".join(edge_pair)]["unknown"] = unknown_edge_data
        edges[" ".join(reversed(edge_pair))]["unknown"] = deepcopy(unknown_edge_data)
    for edge_pair in unblocked_edges:
        unknown_edge_data = {"edge": {"actual": True}}
        edges[" ".join(edge_pair)]["unknown"] = unknown_edge_data
        edges[" ".join(reversed(edge_pair))]["unknown"] = deepcopy(unknown_edge_data)

    return {
        "bidirectional": False,
        "edges": edges
    }


def create_hospital_names(hospitals):
    return ["hospital{}-{}".format(x, y) for x, y in hospitals]


def create_building_names(size, hospitals):
    coords = [(x, y) for x in range(size.x) for y in range(size.y)]
    return ["building{}-{}".format(x, y) for x, y in coords if (x, y) not in hospitals]


if __name__ == "__main__":
    args = parser().parse_args()
    print(args)
    create_problem(**vars(args))
