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
    FinishActionsAndUseStatePredictionExecutor, FinishActionsExecutor
from planner import Planner
from new_simulator import Simulator

import problem_parser
import logger


def parser():
    p = argparse.ArgumentParser(description="Simulator to run planner and carry out plan")
    p.add_argument("problem_file")
    p.add_argument("--planning-time", "-t", type=decimal.Decimal, default="nan")
    p.add_argument("--log-directory", "-l", default="logs")
    return p


if __name__ == "__main__":

    log = logger.StyleAdapter(logging.getLogger())

    args = parser().parse_args()
    log.info(args)
    log_file_name = logger.Logger.get_log_file_name(args.problem_file, args.planning_time)
    log.info("log: {}", log_file_name)

    model = problem_parser.decode(args.problem_file)
    executor = PartialExecutionOnObservationExecutor(args.planning_time)
    planner = Planner(args.planning_time)

    with logger.Logger(log_file_name, args.log_directory) as logger:
        simulator = Simulator(model, executor, planner, logger)
        result = simulator.run()
        simulator.print_results(logger)

    if not result:
        exit(1)