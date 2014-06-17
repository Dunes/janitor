from collections import Iterable
from numbers import Number
from itertools import dropwhile
import action

from planning_exceptions import IncompletePlanException

_action_map = {
	"move": action.Move,
	"clean": action.Clean,
	"extra-clean": action.ExtraClean,
}

def _is_not_starting_action(line):
	return not line.startswith("0.000: ")

def _is_not_plan_cost(line):
	return not line.startswith("; Cost: ")	

def decode_plan_from_optic(data_input, report_incomplete_plan=True):
	#read until first action
	return decode_plan(dropwhile(_is_not_starting_action, data_input), report_incomplete_plan)
	

def decode_plan(data_input, report_incomplete_plan=True):
	
	line = None
	for line in data_input:
		if line == "\n":
			break
		if line[-1] != "\n":
			raise IncompletePlanException("action not terminated properly")
		items = line.split(" ")
		start_time = float(items[0][:-1])
		end_time = float(items[-1][1:-2])
		action_name = items[1].strip("()")
		arguments = tuple(i.strip("()") for i in items[2:-2])
		action =  _action_map[action_name](start_time, end_time, *arguments)
		yield action
	if report_incomplete_plan and line != "\n":
		raise IncompletePlanException("possible missing action")

def encode_problem_to_file(filename, model):
	with (open(filename, "w") if isinstance(filename, str) else filename) as fh:
		encode_problem(fh, model)

def encode_problem(out, model):

	has_metric = model.has_key("metric")
	
	#_encode_preamble(out, model["problem"], model["domain"], has_metric)
	_encode_preamble(out, "problem-name", model["domain"], has_metric)

	_encode_objects(out, model["agents"].keys() + model["nodes"].keys())

	_encode_init(out, model["agents"], model["nodes"], model["graph"], model["assumed-values"])

	_encode_goal(out, model["goal"])

	if has_metric:
		_encode_metric(out, model["metric"])	

	# postamble
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
	for obj in objects:
		out.write(" ")
		out.write(obj)
	out.write(")\n")

def _encode_init(out, agents, nodes, graph, assumed_values):
	out.write("(:init ")
	_encode_init_helper(out, agents, assumed_values)
	_encode_init_helper(out, nodes, assumed_values)
	_encode_graph(out, graph)
	out.write(") ")
	
def _encode_init_helper(out, items, assumed_values):	
	for object_name, object_values in items.iteritems():
		if not object_values.has_key("known"):
			_encode_init_values(out, object_name, object_values)
		else :
			_encode_init_values(out, object_name, object_values["known"])
			_encode_init_values(out, object_name, object_values["unknown"], assumed_values, _unknown_value_getter)
			
def _encode_init_values(out, object_name, object_values, assumed_values=None, value_getter=(lambda x, _0, _1: x)):
	for value_name, possible_values in object_values.iteritems():
		value = value_getter(possible_values, value_name, assumed_values)
		if value is False:
			pass
		elif value is True:
			_encode_predicate(out, (value_name, object_name))
		elif isinstance(value, Number):
			_encode_function(out, (value_name, object_name), value)
		elif isinstance(value, Iterable):
			if isinstance(value[-1], Number):
				pred_values = (value_name,) + tuple(x if not isinstance(x,bool) else object_name for x in value[:-1])
				_encode_function(out, pred_values, value[-1])
			else:
				pred_values = (value_name,) + tuple(x if not isinstance(x,bool) else object_name for x in value)
				_encode_predicate(out, pred_values)

def _unknown_value_getter(possible_values, object_name, assumed_values):
	if possible_values.has_key("assumed"):
		return possible_values["assumed"]
	value = assumed_values[object_name]
	if possible_values.has_key(value):
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

def _encode_graph(out, graph):

	for node0, node1, value in graph["edges"]:
		_encode_predicate(out, ("edge", node0, node1))
		_encode_function(out, ("distance", node0, node1), value)

	if graph["bidirectional"]:
		for node0, node1, value in graph["edges"]:
			_encode_predicate(out, ("edge", node1, node0))
			_encode_function(out, ("distance", node1, node0), value)	

def _encode_goal(out, goals):
	out.write("(:goal (and ")
	if isinstance(goals, list):
		for goal in goals:
			_encode_predicate(out, goal)		
	else: # is dict
		for goal in goals["hard-goals"]:
			_encode_predicate(out, goal)
		if goals.has_key("preferences"):
			for preference in goals["preferences"]:
				_encode_predicate(out, ["preference"] + preference)
	out.write("))\n")
	
def _encode_metric(out, metric):
	out.write("(:metric ")
	out.write(metric["type"])
	out.write(" ")
	_encode_predicate(out, metric["predicate"])
	out.write(")\n")
