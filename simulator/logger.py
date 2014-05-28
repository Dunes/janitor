from os.path import join, basename, splitext

class Logger(object):

	@classmethod
	def get_log_file_name(cls, problem_name, planning_time, wait_for_observations):
		wait = "wait" if wait_for_observations else "no-wait"
		return splitext(basename(problem_name))[0]+("-planning-time({})-{}.log").format(planning_time, wait)

	@classmethod
	def get_plan_log_file_name(cls, log_file_name):
		name, ext = splitext(log_file_name)
		return name + "-plans" + ext
	
	def __init__(self, log_file_name, working_directory="./logs"):
		self.log_file_name = join(working_directory, log_file_name)
		self.plan_log_file_name = join(working_directory, self.get_plan_log_file_name(log_file_name))
		self.log = None 
		self.plan_log = None
	
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
