from os.path import join, basename, splitext, isdir
from os import makedirs

from logging import LoggerAdapter
from inspect import getargspec

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
		except FileExistsError: # Python >2.5
			if isdir(path):
				pass
			else: raise

	def log_property(self, name, value, stringify=str):
		if not self.log:
			self.log = open(self.log_file_name, "w")
			self.log.write("{\n")
		self.log.write(repr(str(name)))
		self.log.write(": ")
		self.log.write(stringify(value))
		self.log.write(",\n")

	def log_plan(self, plan):
		if not self.plan_log:
			self.plan_log = open(self.plan_log_file_name, "w")
		self.plan_log.write(repr(plan))
		self.plan_log.write("\n")

	def close(self):
		error = None
		try:
			if self.log and not self.log.closed:
				self.log.write("}\n")
				self.log.close()
		except IOError as e:
			error = e
		if self.plan_log and not self.plan_log.closed:
			self.plan_log.close()
		if error:
			raise error

	def __exit__(self, type_, value, tb):
		self.close()

	def __enter__(self):
		return self

class BraceMessage:
	def __init__(self, fmt, args, kwargs):
		self.fmt = fmt
		self.args = args
		self.kwargs = kwargs

	def __str__(self):
		return str(self.fmt).format(*self.args, **self.kwargs)

class StyleAdapter(LoggerAdapter):
	def __init__(self, logger):
		self.logger = logger

	def log(self, level, msg, *args, **kwargs):
		if self.isEnabledFor(level):
			msg, log_kwargs = self.process(msg, kwargs)
			self.logger._log(level, BraceMessage(msg, args, kwargs), (), **log_kwargs)

	def process(self, msg, kwargs):
		return msg, {key: kwargs[key] for key in getargspec(self.logger._log).args[1:] if key in kwargs}