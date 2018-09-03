import re
from itertools import dropwhile
from io import TextIOWrapper, RawIOBase, BufferedIOBase

from accuracy import quantize
from planning_exceptions import IncompletePlanException
from accuracy import as_next_end_time

line_start_pattern = re.compile(r'\d+\.\d{3}:')
class_name_pattern = re.compile(r"[A-Z][a-z]*")


def create_action_map(*actions):
    return {pddl_action_name(a): a for a in actions}


def pddl_action_name(action_):
    python_name = action_.__name__
    return "-".join(match.lower() for match in class_name_pattern.findall(python_name))


def _is_not_starting_action(line):
    return not line_start_pattern.match(line)


def _is_not_plan_cost(line):
    return not line.startswith("; Cost: ")


class PlanDecoder:

    def __init__(self, action_map):
        self.action_map = action_map

    def decode_plan_from_optic(self, data_input, time, report_incomplete_plan=True):
        # read until first action
        return self.decode_plan(dropwhile(_is_not_starting_action, data_input), time, report_incomplete_plan)

    def decode_plan(self, data_input, time, report_incomplete_plan=True):
        line = None
        for line in data_input:
            match = line_start_pattern.match(line)
            if not match:
                break
            if line[-1] != "\n":
                raise IncompletePlanException("action not terminated properly")
            items = line.split(" ")
            start_time = quantize(items[0][:-1]) + time
            duration = quantize(items[-1][1:-2])
            action_name = items[1].strip("()")
            arguments = tuple(i.strip("()") for i in items[2:-2])
            action_ = self.action_map[action_name](start_time, duration, *arguments)
            if action_ is not None:
                yield action_
        if report_incomplete_plan and line != "\n":
            raise IncompletePlanException("possible missing action")


def get_text_file_handle(filename):
    if isinstance(filename, str):
        return open(filename, "w")
    elif isinstance(filename, (RawIOBase, BufferedIOBase)):
        return TextIOWrapper(filename)
    else:
        return filename
