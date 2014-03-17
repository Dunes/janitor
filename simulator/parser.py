from collections import Iterable
import json
from numbers import Number

class Json(object):

	def decode(filename):
		with open(filename) as fh:
			obj = json.load(fh)	
		return obj

	def encode(filename):
		with open(filename) as fh:
			obj = json.dump(fh)	

class Pddl(object):

	def encode_file(obj, filename):
		with open(filename, "w") as fh:
			encode(obj, fh)
	
	def encode(obj, out):
		
		_encode_preamble(out, obj["problem"], obj["domain"])
	
		_encode_objects(out, obj["agents"].keys() + obj["nodes"].keys())
	
		_encode_init(out, obj["agents"], obj["nodes"], obj["graph"], obj["assumed-values"])
	
		_encode_goal(out, obj["goal"])
	
	#	_encode_metric(out)

		# postamble
		out.write(")")


	def _encode_preamble(out, problem_name, domain_name):
		out.write("(define (problem ")
		out.write(problem_name)
		out.write(") (:domain ")
		out.write(domain_name)
		out.write(")\n")

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
			out.write(arg)
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
		for goal in goals:
			_encode_predicate(out, goal)
		out.write("))\n")
		
	def _encode_metric(out):
		raise Exception("not implemented yet")
