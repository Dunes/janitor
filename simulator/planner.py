from subprocess import Popen, PIPE
import pddl_parser
import tempfile
from os.path import join as path_join

working_directory = ".."

tempfile.tempdir = path_join(working_directory, "temp_problems")
planner_location = "./optic-cplex"
domain_file = "./janitor/janitor-domain.pddl"

def get_plan(model):
	problem_file = create_problem_file(model)
	args = planner_location, "-N", domain_file, problem_file # N arg stops planner after first plan is found -- remove later
	p = Popen(args, stdout=PIPE, cwd=working_directory)
	plan = list(pddl_parser.decode_plan_from_optic(p.stdout))
	p.terminate()
	return plan
	
def create_problem_file(model):
	fh = tempfile.NamedTemporaryFile(mode="w", prefix="problem-", suffix=".pddl", delete=False)
	pddl_parser.encode_problem_to_file(fh, model)
	return fh.name
