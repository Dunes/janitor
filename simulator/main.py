#! /usr/bin/env python3
"""
Created on 12 Jul 2014

@author: jack
"""

import argparse
import decimal
import logging.config
import importlib

logging.config.fileConfig("logging.conf")

from planner import Planner

import problem_parser
import logger

log = logger.StyleAdapter(logging.getLogger())


domain_template = "../janitor/{}-domain.pddl"


def parser():
    p = argparse.ArgumentParser(description="Simulator to run planner and carry out plan")
    p.add_argument("--domain-file", "-d")
    p.add_argument("problem_file")
    p.add_argument("--planning-time", "-t", type=decimal.Decimal, default="nan",
        help="The amount of time to spend planning")
    p.add_argument("--log-directory", "-l", default="logs")
    return p


def run_old_simulator():
    from new_simulator import Simulator
    import executor

    args = parser().parse_args()
    log.info(args)
    log_file_name = logger.Logger.get_log_file_name(args.problem_file, args.planning_time)
    log.info("log: {}", log_file_name)

    model = problem_parser.decode(args.problem_file)
    executor_ = executor.GreedyPlanHeuristicExecutor(args.planning_time)
    planner = Planner(args.planning_time,
                      domain_file=args.domain_file or domain_template.format(model["domain"]))

    with logger.Logger(log_file_name, args.log_directory) as result_logger:
        simulator = Simulator(model, executor_, planner, result_logger)
        try:
            result = simulator.run()
        finally:
            simulator.print_results(result_logger)

    if not result:
        exit(1)


def run_single_agent_replan_simulator():
    from singleagent.simulator import Simulator
    from singleagent.executor import AgentExecutor, CentralPlannerExecutor

    args = parser().parse_args()
    log.info(args)
    log_file_name = logger.Logger.get_log_file_name(args.problem_file, args.planning_time)
    log.info("log: {}", log_file_name)

    # load model
    model = problem_parser.decode(args.problem_file)
    decoder = importlib.import_module(model["domain"]).plan_decoder

    # create planners
    central_planner = Planner(args.planning_time,
        decoder=decoder,
        domain_file=domain_template.format(model["domain"]))
    local_planner = Planner(args.planning_time,
        decoder=decoder,
        domain_file=domain_template.format("janitor-single"))

    # create and setup executors
    agent_executors = [AgentExecutor(agent=agent_name, planning_time=args.planning_time)
                       for agent_name in model["agents"]]
    planning_executor = CentralPlannerExecutor(agent="planner",
                                               planning_time=args.planning_time,
                                               executor_ids=[e.id for e in agent_executors],
                                               agent_names=[e.agent for e in agent_executors],
                                               central_planner=central_planner,
                                               local_planner=local_planner)
    for e in agent_executors:
        e.planner_id = planning_executor.id

    # setup simulator
    executors = dict({e.agent: e for e in agent_executors},
                     planner=planning_executor)
    simulator = Simulator(model, executors)

    # run simulator
    with logger.Logger(log_file_name, args.log_directory) as result_logger:
        try:
            result = simulator.run()
        finally:
            simulator.print_results(result_logger)

    if not result:
        exit(1)


def run_roborescue_simulator():
    from roborescue import plan_decoder, problem_encoder
    from roborescue.simulator import Simulator
    from roborescue.executor import EventExecutor, MedicExecutor, PoliceExecutor, CentralPlannerExecutor
    domain_template = "../roborescue/{}-domain.pddl"

    args = parser().parse_args()
    log.info(args)
    log_file_name = logger.Logger.get_log_file_name(args.problem_file, args.planning_time)
    log.info("log: {}", log_file_name)

    # load model
    model = problem_parser.decode(args.problem_file)
    decoder = plan_decoder
    # add bidirectionality
    if model["graph"].get("bidirectional"):
        edges = model["graph"]["edges"]
        from copy import deepcopy
        for key in list(edges):
            new_key = " ".join(reversed(key.split(" ")))
            edges[new_key] = deepcopy(edges[key])
    # add agents key
    from itertools import chain
    model["agents"] = dict(chain(model["objects"]["police"].items(), model["objects"]["medic"].items()))

    # create planners
    central_planner = Planner(args.planning_time,
                              decoder=decoder,
                              problem_encoder=problem_encoder,
                              domain_file=domain_template.format(model["domain"]))

    local_planner = Planner(args.planning_time,
                            decoder=decoder,
                            problem_encoder=problem_encoder,
                            domain_file=domain_template.format(model["domain"]))

    # create and setup executors
    agent_executors = [PoliceExecutor(agent=agent_name, planning_time=args.planning_time)
                       for agent_name in model["objects"]["police"]] \
                      + [MedicExecutor(agent=agent_name, planning_time=args.planning_time)
                         for agent_name in model["objects"]["medic"]]
    event_executor = EventExecutor(events=model["events"])
    planning_executor = CentralPlannerExecutor(
        agent="planner", planning_time=args.planning_time, executor_ids=[e.id for e in agent_executors],
        agent_names=[e.agent for e in agent_executors], central_planner=central_planner, local_planner=local_planner,
        event_executor=event_executor)

    for e in agent_executors:
        e.planner_id = planning_executor.id

    # setup simulator
    executors = dict({e.agent: e for e in agent_executors},
                     planner=planning_executor, event_executor=event_executor)
    simulator = Simulator(model, executors)

    # run simulator
    with logger.Logger(log_file_name, args.log_directory) as result_logger:
        try:
            result = simulator.run()
        finally:
            simulator.print_results(result_logger)
            problem_parser.encode("temp_problems/final_model.json", simulator.model)

    if not result:
        exit(1)

if __name__ == "__main__":
    run_roborescue_simulator()
