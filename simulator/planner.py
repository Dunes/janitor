from subprocess import Popen, PIPE
from pddl_parser import decode_plan_from_optic, encode_problem_to_file
import tempfile
from os.path import join as path_join
from threading import Timer
from time import time
from math import isnan
from planning_exceptions import NoPlanException, IncompletePlanException

class Planner(object):
	
	def __init__(self, planning_time, planner_location="./optic-cplex", domain_file="./janitor/janitor-domain.pddl",
			working_directory=".."):
		self.planning_time = planning_time if not isnan(planning_time) else "till_first_plan"
		self.planner_location = planner_location
		self.domain_file = domain_file
		self.working_directory = working_directory
		
		tempfile.tempdir = path_join(working_directory, "temp_problems")
		

	def get_plan(self, model):
		problem_file = self.create_problem_file(model)
	
		args = self.planner_location, self.domain_file, problem_file
		if self.planning_time == "till_first_plan":
			args = self.planner_location, "-N", self.domain_file, problem_file
			p = Popen(args, stdout=PIPE, cwd=self.working_directory)
			plan = list(decode_plan_from_optic(p.stdout, report_incomplete_plan=False))
		else:
			args = self.planner_location, self.domain_file, problem_file
			p = Popen(args, stdout=PIPE, cwd=self.working_directory)				
			Timer(self.planning_time, p.terminate).start()
		
			plan = None
			while True:
				try:
					plan = list(decode_plan_from_optic(p.stdout, report_incomplete_plan=True))
				except IncompletePlanException:
					break

		if not plan:
			raise NoPlanException()
		return plan
	
	def get_plan_and_time_taken(self, model):
		start = time()
		plan = self.get_plan(model)
		end = time()
		return plan, end - start
	
	def create_problem_file(self, model):
		fh = tempfile.NamedTemporaryFile(mode="w", prefix="problem-", suffix=".pddl", delete=False)
		encode_problem_to_file(fh, model)
		return fh.name
