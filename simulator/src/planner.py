from functools import wraps
from subprocess import Popen, PIPE
from pddl_parser import decode_plan_from_optic, encode_problem_to_file
import tempfile
from os.path import join as path_join
from threading import Timer, Thread, Lock
from time import time
from math import isnan
from planning_exceptions import NoPlanException, IncompletePlanException
from accuracy import quantize
from logging import getLogger
from logger import StyleAdapter


log = StyleAdapter(getLogger(__name__))


_lock = Lock()


def synchronized(func):
    @wraps(func)
    def f(*args, **kwargs):
        try:
            if not _lock.acquire(blocking=False):
                log.warning("Trying to run planner when another instance of planner is running")
                _lock.acquire()
            return func(*args, **kwargs)
        finally:
            _lock.release()
    return f


class Planner(object):

    def __init__(self, planning_time, planner_location="../optic-cplex", domain_file="../janitor/janitor-domain.pddl",
            working_directory=".", encoding="UTF-8"):
        self.planning_time = planning_time if not isnan(planning_time) else "till_first_plan"
        self.planner_location = planner_location
        self.domain_file = domain_file
        self.working_directory = working_directory
        self.encoding = encoding

        tempfile.tempdir = path_join(working_directory, "temp_problems")

    @synchronized
    def get_plan(self, model, duration=None, agent="all", goals=None):
        # problem_file = self.create_problem_file(model)
        problem_file = "/dev/stdin"
        report = True
        args = self.planner_location, self.domain_file, problem_file
        single_pass = False
        if duration is None:
            duration = self.planning_time
        elif duration == 0:
            duration = 2.
            args = self.planner_location, "-N", self.domain_file, problem_file
            report = False
            single_pass = True

        p = Popen(args, stdin=PIPE, stdout=PIPE, cwd=self.working_directory)
        Thread(target=encode_problem_to_file, name="problem-writer", args=(p.stdin, model, agent, goals)).start()
        timer = Timer(float(duration), p.terminate)
        timer.start()

        plan = None
        # run loop only once when duration is 0
        while True:
            try:
                plan = list(decode_plan_from_optic(self.decode(p.stdout), report_incomplete_plan=report))
            except IncompletePlanException:
                break
            if single_pass:
                break
        timer.cancel()
        p.wait(1)

        if plan is not None:
            return plan
        if report:
            raise NoPlanException()
        if single_pass:
            return []
        raise RuntimeError("Illegal state")

    def get_plan_and_time_taken(self, model, duration=None, agent="all"):
        start = time()
        plan = self.get_plan(model, duration, agent)
        end = time()
        return plan, quantize(end - start)

    @staticmethod
    def create_problem_file(model):
        fh = tempfile.NamedTemporaryFile(mode="w", prefix="problem-", suffix=".pddl", delete=False)
        encode_problem_to_file(fh, model)
        return fh.name

    def decode(self, data_stream):
        for line in data_stream:
            yield line.decode(self.encoding)
