from functools import wraps
from subprocess import Popen, PIPE
import tempfile
from io import TextIOWrapper
from os.path import join as path_join, basename, splitext
from threading import Timer, Thread, Lock
from time import time as _time
from math import isnan
from logging import getLogger

from planning_exceptions import NoPlanException, IncompletePlanException
from accuracy import quantize
from logger import StyleAdapter

log = StyleAdapter(getLogger(__name__))


_lock = Lock()


def synchronized(lock):
    def _synchronized(func):
        @wraps(func)
        def f(*args, **kwargs):
            try:
                if not lock.acquire(blocking=False):
                    log.warning("Trying to run planner when another instance of planner is running")
                    lock.acquire()
                return func(*args, **kwargs)
            finally:
                lock.release()
        return f
    return _synchronized


class Planner(object):

    def __init__(self, planning_time, decoder, problem_encoder, domain_file, planner_location="../optic-cplex",
                 working_directory=".", encoding="UTF-8"):
        self.planning_time = planning_time if not isnan(planning_time) else "till_first_plan"
        self.planner_location = planner_location
        self.domain_file = domain_file
        self.working_directory = working_directory
        self.encoding = encoding
        self.decoder = decoder
        self.problem_encoder = problem_encoder

        tempfile.tempdir = path_join(working_directory, "temp_problems")

    @synchronized(_lock)
    def get_plan(self, model, *, duration, agent, goals, metric, time, events):
        log.debug("Planner.get_plan() duration={}, agent={!r}, goals={}, metric={}, time={}, events={}", duration, agent,
            goals, metric, time, events)
        problem_file = self.create_problem_file(model, agent, goals, metric, time, events)
        # problem_file = "/dev/stdin"
        report = True
        args = [self.planner_location, self.domain_file, problem_file]
        single_pass = False
        if duration == 0:
            duration += 2
            args = self.planner_location, "-N", self.domain_file, problem_file
            report = False
            single_pass = True

        p = Popen(args, stdin=None, stdout=PIPE, cwd=self.working_directory)
        # Thread(target=self.problem_encoder.encode_problem_to_file, name="problem-writer",
        #        args=(p.stdin, model, agent, goals, metric, time, events)).start()
        timer = Timer(float(duration), p.terminate)
        timer.start()

        plan = None
        # run loop only once when duration is 0
        with TextIOWrapper(p.stdout) as process_output:
            while True:
                try:
                    plan = list(self.decoder.decode_plan_from_optic(
                        process_output, time=time + duration, report_incomplete_plan=report))
                except IncompletePlanException:
                    break
                if single_pass:
                    break
            timer.cancel()
        p.wait(1)

        if plan is not None:
            root, ext = splitext(basename(problem_file))
            with open("logs/roborescue/plans/{}.plan".format(root), "w") as f:
                f.write(repr(plan))
            return plan
        if report:
            raise NoPlanException
        if single_pass:
            return []
        raise RuntimeError("Illegal state")

    def get_plan_and_time_taken(self, model, *, duration, agent, goals, metric, time, events):
        start = _time()
        plan = self.get_plan(model, duration=duration, agent=agent, goals=goals, metric=metric, time=time, events=events)
        end = _time()
        return plan, min(quantize(end - start), duration)

    def create_problem_file(self, model, agent, goals, metric, time, events):
        import datetime
        now = datetime.datetime.utcnow().time().isoformat()
        prefix = "{}-{}-{}-{}-".format(model["domain"], agent, time, now)
        fh = tempfile.NamedTemporaryFile(mode="w", prefix=prefix, suffix=".pddl", delete=False)
        self.problem_encoder.encode_problem_to_file(fh, model, agent, goals, metric, time, events)
        return fh.name
