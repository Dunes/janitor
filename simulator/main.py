#! /usr/bin/env python3
"""
Created on 12 Jul 2014

@author: jack
"""

import argparse
import decimal
import logging.config

logging.config.fileConfig("logging.conf")

import problem_parser
import logger
import simulator


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
    model = problem_parser.decode(args.problem_file)
    log_file_name = logger.Logger.get_log_file_name(args.problem_file, args.planning_time)
    log.info("log: {}", log_file_name)
    with logger.Logger(log_file_name, args.log_directory) as logger:
        result = simulator.run_simulation(model, logger, args.planning_time)
    if not result:
        exit(1)