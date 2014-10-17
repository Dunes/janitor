#! /usr/bin/python3

from problem_creator import Point, ActualMinMax, create_problem, create_problem_irreversible
from random import sample
from itertools import product
from os.path import join


def generate_problem_name(size, dirtiness, edge_length, agents, starting_location, percentage_extra_dirty):
    keys = dict(locals())
    format_string = "auto-size({size.x},{size.y})-dirt({dirtiness.actual},{dirtiness.min},{dirtiness.max})-" \
        "edge({edge_length})-agents({agents})-start({starting_location})-extra_dirt({percentage_extra_dirty:.0%})"
    return format_string.format(**keys)


def generate_problem_name_irreversible(size, dirtiness, edge_length, agents, starting_location, percentage_extra_dirty,
                                       number_occupied):
    keys = dict(locals())
    format_string = "auto-size({size.x},{size.y})-dirt({dirtiness.actual},{dirtiness.min},{dirtiness.max})-" \
        "edge({edge_length})-agents({agents})-start({starting_location})-extra_dirt({percentage_extra_dirty:.0%})-" \
        "occupied({number_occupied})"
    return format_string.format(**keys)


def get_centre(size):
    return Point(*(int(i/2.0 - 0.5) for i in size))


def generate_random_locations(size, sample_size=None, percentage=None, exclude=()):
    if None not in (sample_size, percentage):
        raise ValueError("can't have both sample_size and percentage set")
    elif sample_size is None and percentage is None:
        raise ValueError("must set either sample_size or percentage set")

    locations = set(product(range(size.x), range(size.y))).difference(exclude)
    if percentage is not None:
        sample_size = int(round(percentage * size.x * size.y))
    return [Point(*p) for p in sample(locations, sample_size)]


def run():

    repeats = 10

    size_types = (
        # Point(3,3),
        Point(4, 4),
        Point(1, 16),
        Point(2, 8),
#        Point(5,5),
#        Point(6,6),
#        Point(7,7),
#        Point(10,10),
    )
    dirtiness_types = (
        ActualMinMax("random", 20, 40),
        ActualMinMax("random", 30, 60),
        ActualMinMax("random", 40, 80),
    )
    edge_length_types = (20,)
    agents_types = (3, 5, 7,)
    starting_location_types = ("centre",)  # empty_rooms and agent_start
    percentage_extra_dirty_types = (0.2,)
    number_occupied_types = (2,)

    output = "generated"
    assume_clean = False
    problem_name = "generated"
    # domain = "janitor"
    domain = "irreversible-action"

    problem_dir = "problems/irreversible"

    for data in product(size_types, dirtiness_types, edge_length_types,
                agents_types, starting_location_types, percentage_extra_dirty_types, number_occupied_types):

        size, dirtiness, edge_length, agents, starting_location, percentage_extra_dirty, number_occupied = data

        problem_name = generate_problem_name_irreversible(*data)

        agent_start = get_centre(size) if starting_location == "centre" else starting_location
        empty_rooms = (agent_start,)

        for i in range(repeats):
            output = join(problem_dir, problem_name + "-id({}).json".format(i))

            extra_dirty_rooms = generate_random_locations(size, percentage=percentage_extra_dirty, exclude=empty_rooms)
            occupied_rooms = generate_random_locations(size, sample_size=number_occupied, exclude=empty_rooms)

            create_problem_irreversible(output, size, dirtiness, assume_clean,
                empty_rooms, edge_length, agents,
                agent_start, problem_name, domain, extra_dirty_rooms, occupied_rooms)

if __name__ == "__main__":
    run()
