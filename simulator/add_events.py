import glob
import json
import os.path
import pathlib
import sys

sys.path.append("./src")

import problem_creator

problem_dir = "/home/jack/work/simulator/problems/roborescue/quantitative/auto"

def get_problem_name(path):
    filename = os.path.basename(path)
    start = filename.index("-planning_time")
    problem_filename = filename[:start] + ".json"
    new_path = os.path.join(problem_dir, problem_filename)
    assert os.path.exists(new_path)
    return new_path

result_files = glob.glob("robologs/blocked*.log")
for path in result_files:
    problem_filename = get_problem_name(path)
    
    with open(path) as f:
        result = json.loads(f.read())
    with open(problem_filename) as f:
        model = json.loads(f.read())
   
    number_of_civs = len(model["objects"]["civilian"])
    end_simulation_time = result["end_simulation_time"]
    events = problem_creator.create_death_events(number_of_civs, end_simulation_time)
    model["events"].extend(events)
    
    new_problem_filename = problem_filename.replace("-without-", "-with-")
    data = json.dumps(model, indent=4)
    with open(new_problem_filename, "w") as f:
        f.write(data)
