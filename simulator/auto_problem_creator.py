from problem_creator import Point, ActualMinMax, create_problem
from random import uniform, sample
from itertools import product
from os.path import join

def generate_problem_name(size, dirtiness, edge_length, agents, starting_location, percentage_extra_dirty):
	keys = dict(locals())
	format_string = "auto-size({size.x},{size.y})-dirt({dirtiness.actual},{dirtiness.min},{dirtiness.max})-" \
		"edge({edge_length})-agents({agents})-start({starting_location})-extra-dirt({percentage_extra_dirty:.0%})"
	return format_string.format(**keys)

def get_centre(size):
	return Point(*(int(i/2. -0.5) for i in size))

def generate_random_locations(size, percentage_extra_dirty, exclude=()):
	locations = set(product(range(size.x), range(size.y))).difference(exclude)
	sample_size = int(round(percentage_extra_dirty * size.x * size.y))
	return [Point(*p) for p in sample(locations, sample_size)]
	

def run():
	size_types = (
		Point(3,3),
		Point(4,4),
		Point(5,5),
		Point(6,6),
		Point(7,7), 
#		Point(10,10),
	)
	dirtiness_types = (
		ActualMinMax("random", 20, 40),
		ActualMinMax("random", 30, 60),
		ActualMinMax("random", 40, 80),
	)
	edge_length_types = (20,)
	agents_types = (3,5,7,)
	starting_location_types = ("centre",) # resource_rooms and agent_start
	percentage_extra_dirty_types = (0.2,)


	output = "generated"
	required_stock = ActualMinMax(0,0,0)
	assume_clean = False
	assume_stocked = True
	violation_weight = "unused"
	carry_capacity = ActualMinMax(0,0,0)
	problem_name = "generated"
	domain = "janitor"

	problem_dir = "problems"

	for data in product(size_types, dirtiness_types, edge_length_types, 
				agents_types, starting_location_types, percentage_extra_dirty_types):
	
		size, dirtiness, edge_length, agents, starting_location, percentage_extra_dirty = data
	
		problem_name = generate_problem_name(*data)
		output = join(problem_dir, problem_name + ".json")
	
		agent_start = get_centre(size) if starting_location == "centre" else starting_location
		resource_rooms = (agent_start,)
		extra_dirty_rooms = generate_random_locations(size, percentage_extra_dirty, exclude=resource_rooms)
	
		create_problem(output, size, dirtiness, required_stock, assume_clean, 
			assume_stocked, resource_rooms, edge_length, violation_weight, agents, 
			agent_start, carry_capacity, problem_name, domain, extra_dirty_rooms)

if __name__ == "__main__":
	run()
