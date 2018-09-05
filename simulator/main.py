#! /usr/bin/env python3
"""
Created on 12 Jul 2014

@author: jack
"""

import argparse
import decimal
import logging.config

logging.config.fileConfig("logging.conf")

from planner import Planner

import problem_parser
import logger

log = logger.StyleAdapter(logging.getLogger())


def parser():
    p = argparse.ArgumentParser(description="Simulator to run planner and carry out plan")
    p.add_argument("--domain-file", "-d")
    p.add_argument("problem_file")
    p.add_argument(
        "--planning-time", "-t", type=decimal.Decimal, default="nan",
        help="The amount of time to spend planning")
    p.add_argument("--log-directory", "-l", default="logs")
    p.add_argument("--simulator", "-s", required=True, choices=list(SIMULATORS))
    p.add_argument("-q", help="ignored")
    return p


def run_old_simulator(domain_template="../janitor/{}-domain.pddl"):
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
            problem_parser.encode("temp_problems/final_model.json", simulator.model)

    if not result:
        exit(1)


def run_single_agent_replan_simulator(args, domain_template="../trucks/{}-domain.pddl"):
    from singleagent.simulator import Simulator
    from singleagent.executor import AgentExecutor, CentralPlannerExecutor
    from trucks_encoder import plan_decoder, problem_encoder

    log.info(args)
    log_file_name = logger.Logger.get_log_file_name(args.problem_file, args.planning_time)
    log.info("log: {}", log_file_name)

    # load model
    model = problem_parser.decode(args.problem_file)

    # create planners
    # decoder, problem_encoder, domain_file=None, planner_location="../optic-cplex",
    #             working_directory=".", encoding="UTF-8", domain_template=None)
    # TODO: args.planning_time goes where?
    central_planner = Planner(
        decoder=plan_decoder,
        problem_encoder=problem_encoder,
        domain_file=domain_template.format(model["domain"]),
    )
    local_planner = None

    # create and setup executors
    agent_executors = []
    for agent_type in ("truck", "boat"):
        agent_executors += [
            AgentExecutor(agent=agent_name, planning_time=args.planning_time, agent_type=agent_type)
            for agent_name in model["objects"][agent_type]
        ]
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
            problem_parser.encode("temp_problems/final_model.json", simulator.model)

    if not result:
        exit(1)


SIMULATORS = {
    "trucks-centralised": run_single_agent_replan_simulator,
}


if __name__ == "__main__":
    args_ = parser().parse_args()
    SIMULATORS[args_.simulator](args_)
