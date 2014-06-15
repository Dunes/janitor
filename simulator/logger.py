from os.path import join, basename, splitext, isdir
from os import makedirs
from errno import EEXIST

class Logger(object):

	@classmethod
	def get_log_file_name(cls, problem_name, planning_time):
		return splitext(basename(problem_name))[0]+("-planning_time({}).log").format(planning_time)

	@classmethod
	def get_plan_log_file_name(cls, log_file_name):
		name, ext = splitext(log_file_name)
		return name + "-plans" + ext
	
	def __init__(self, log_file_name, working_directory="./logs", plans_subdir="plans"):
		self._create_if_not_exists(working_directory)
		self._create_if_not_exists(join(working_directory, plans_subdir))
		self.log_file_name = join(working_directory, log_file_name)
		self.plan_log_file_name = join(working_directory, plans_subdir, self.get_plan_log_file_name(log_file_name))
		self.log = None 
		self.plan_log = None
	
	def _create_if_not_exists(self, path):
		try:
		    makedirs(path)
		except OSError as exc: # Python >2.5
		    if exc.errno == EEXIST and isdir(path):
		        pass
		    else: raise
	
	def log_property(self, name, value):
		if not self.log:
			self.log = open(self.log_file_name, "w")
			self.log.write("{\n")
		self.log.write(repr(str(name)))
		self.log.write(": ")
		self.log.write(repr(value))
		self.log.write(",\n")
	
	def log_plan(self, plan):
		if not self.plan_log:
			self.plan_log = open(self.plan_log_file_name, "w")
		self.plan_log.write(repr(plan))
		self.plan_log.write("\n")
		
	def close(self):
		e = None
		try:
			if self.log and not self.log.closed:
				self.log.write("}\n")
				self.log.close()
		except IOError as e:
			pass
		if self.plan_log and not self.plan_log.closed:
			self.plan_log.close()
		if e:
			raise e
	
	def __exit__(self, type, value, tb):
		self.close()
	
	def __enter__(self):
		return self
