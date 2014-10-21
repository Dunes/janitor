#! /usr/bin/env python3
"""
Created on 12 Jul 2014

@author: jack
"""

import argparse
import decimal
import logging.config

logging.config.fileConfig("logging.conf")

from executor import PartialExecutionOnObservationExecutor, PartialExecutionOnObservationAndStatePredictionExecutor, \
    FinishActionsAndUseStatePredictionExecutor, FinishActionsExecutor, GreedyPlanHeuristicExecutor
from planner import Planner
from new_simulator import Simulator

import problem_parser
import logger

log = logger.StyleAdapter(logging.getLogger())


def parser():
    p = argparse.ArgumentParser(description="Simulator to run planner and carry out plan")
    p.add_argument("--domain-file", "-d")
    p.add_argument("problem_file")
    p.add_argument("--planning-time", "-t", type=decimal.Decimal, default="nan",
        help="The amount of time to spend planning")
    p.add_argument("--log-directory", "-l", default="logs")
    return p


def get_domain_file(model):
    return "../janitor/{}-domain.pddl".format(model["domain"])


def run():
    args = parser().parse_args()
    log.info(args)
    log_file_name = logger.Logger.get_log_file_name(args.problem_file, args.planning_time)
    log.info("log: {}", log_file_name)

    model = problem_parser.decode(args.problem_file)
    executor = GreedyPlanHeuristicExecutor(args.planning_time)
    planner = Planner(args.planning_time, domain_file=args.domain_file or get_domain_file(model))

    with logger.Logger(log_file_name, args.log_directory) as result_logger:
        simulator = Simulator(model, executor, planner, result_logger)
        try:
            result = simulator.run()
        finally:
            simulator.print_results(result_logger)

    if not result:
        exit(1)

if __name__ == "__main__":
    run()