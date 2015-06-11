__author__ = 'jack'

import unittest

try:
    from .. util.builder import ModelBuilder
except SystemError:
    import sys
    sys.path.append("..")
    from util.builder import ModelBuilder
from problem_creator import ActualMinMax, Point, create_room, create_goal

from decimal import Decimal
from operator import attrgetter
from os import getcwd
from os.path import join, exists

from action import Move, Clean, ExtraClean, Observe, Plan
from planner import Planner
from action_state import ActionState, ExecutionState
from singleagent.executor import AgentExecutor, CentralPlannerExecutor
from singleagent.simulator import Simulator

zero = Decimal(0)
ten = Decimal(10)


class TestExecutorKnowledgePassing(unittest.TestCase):

    def setUp(self):
        # create model
        dirtiness = ActualMinMax(ten, zero, ten)
        self.model = ModelBuilder() \
            .with_agent("agent1", at="rm1").with_agent("agent2", at="rm1") \
            .with_edge("rm1", "rm2", ten).with_edge("rm1", "rm3", ten) \
            .with_edge("rm2", "rm1", ten).with_edge("rm2", "rm3", ten) \
            .with_edge("rm3", "rm1", ten).with_edge("rm3", "rm2", ten) \
            .with_node("rm1", value=create_room(dirtiness, False)) \
            .with_node("rm2", value=create_room(dirtiness, False)) \
            .with_node("rm3", value=create_room(dirtiness, False)) \
            .with_assumed_values(
                {"dirty": True, "cleaned": False, "dirtiness": "max", "extra-dirty": False}
            ).model
        self.model["domain"] = "janitor"

        # make rm2 extra dirty
        self.model["nodes"]["rm2"]["unknown"]["dirty"]["actual"] = False
        self.model["nodes"]["rm2"]["unknown"]["extra-dirty"]["actual"] = True

        Observe(zero, "agent1", "rm1").apply(self.model)

        # goal
        goal = create_goal(Point(2, 2), [], [])
        goal["hard-goals"] = [g for g in goal["hard-goals"] if g[1] != "rm4"]
        self.model["goal"] = goal

        # create executors
        wd = join(getcwd(), "../..")
        assert exists(join(wd, "../optic-cplex"))
        local_planner = Planner(ten, working_directory=wd, domain_file="../janitor/janitor-single-domain.pddl")

        self.agent1_executor = AgentExecutor(agent="agent1", planning_time=ten, planner_id=None)
        self.agent2_executor = AgentExecutor(agent="agent2", planning_time=ten, planner_id=None)
        self.planner_executor = CentralPlannerExecutor(
            agent="planner", planning_time=ten, executor_ids=[self.agent1_executor.id, self.agent2_executor.id],
            agent_names=["agent1", "agent2"], central_planner=None, local_planner=local_planner
        )
        self.agent1_executor.planner_id = self.planner_executor.id
        self.agent2_executor.planner_id = self.planner_executor.id

    def create_plan(self, include_observations):
        agent1_plan = [
            Clean(zero, ten, "agent1", "rm1"),
            Move(ten, ten, "agent1", "rm1", "rm2"),
            Move(Decimal(40), ten, "agent1", "rm2", "rm3"),
            Clean(Decimal(50), ten, "agent1", "rm3")
        ]
        agent2_plan = [
            Move(zero, ten, "agent2", "rm1", "rm3"),
            Move(ten, ten, "agent2", "rm3", "rm2")
        ]
        extra_clean = [ExtraClean(Decimal(30), ten, "agent1", "agent2", "rm2")]

        if include_observations:
            observations = [Observe(Decimal(20), "agent1", "rm2"),
                            Observe(Decimal(50), "agent1", "rm3"),
                            Observe(Decimal(10), "agent2", "rm3"),
                            Observe(Decimal(20), "agent2", "rm2")
                            ]
        else:
            observations = []

        return sorted(agent1_plan + agent2_plan + extra_clean + observations, key=attrgetter("start_time"))

    def test_can_carry_out_simple_plan(self):

        # given a lot of stuff
        plan = self.create_plan(include_observations=False)

        # initial observations -- see everything
        self.model["agents"]["agent1"]["at"][1] = "rm3"
        Observe(zero, "agent1", "rm3").apply(self.model)
        self.model["agents"]["agent1"]["at"][1] = "rm2"
        Observe(zero, "agent1", "rm2").apply(self.model)
        self.model["agents"]["agent1"]["at"][1] = "rm1"

        # give planner initial plan
        as_ = ActionState(Plan(zero, zero, "planner", plan), zero, ExecutionState.executing)
        self.planner_executor.executing = as_
        self.planner_executor.notify_action_finishing(as_, self.model)

        simulator = Simulator(self.model,
                              {"agent1": self.agent1_executor,
                               "agent2": self.agent2_executor,
                               "planner": self.planner_executor
                               })
        # when
        simulator.run()

        # then assert goal is succeeded
        self.assertTrue(simulator.is_goal_in_model())

    def test_new_knowledge_means_clean_action_brought_forward(self):
        """new knowledge in rm2 should only cause agent0 to do a local replan"""
        # given a lot of stuff
        plan = self.create_plan(include_observations=True)

        # give planner initial plan
        as_ = ActionState(Plan(zero, zero, "planner", plan), zero, ExecutionState.executing)
        self.planner_executor.executing = as_
        self.planner_executor.notify_action_finishing(as_, self.model)

        simulator = Simulator(self.model,
                              {"agent1": self.agent1_executor,
                               "agent2": self.agent2_executor,
                               "planner": self.planner_executor
                               })
        # when
        simulator.run()

        # then assert goal is succeeded
        self.assertTrue(simulator.is_goal_in_model())


class TestFullProblem(unittest.TestCase):

    def setUp(self):
        # create model
        dirtiness = ActualMinMax(ten, zero, ten)
        self.model = ModelBuilder() \
            .with_agent("agent1", at="rm0").with_agent("agent2", at="rm0") \
            .with_edge("rm0", "rm1", ten).with_edge("rm0", "rm1", ten) \
            .with_edge("rm1", "rm2", ten).with_edge("rm1", "rm3", ten) \
            .with_edge("rm2", "rm1", ten).with_edge("rm2", "rm3", ten) \
            .with_edge("rm3", "rm1", ten).with_edge("rm3", "rm2", ten) \
            .with_node("rm0", value=create_room(ActualMinMax(zero, zero, ten), False)) \
            .with_node("rm1", value=create_room(dirtiness, False)) \
            .with_node("rm2", value=create_room(dirtiness, False)) \
            .with_node("rm3", value=create_room(dirtiness, False)) \
            .with_assumed_values(
                {"dirty": True, "cleaned": False, "dirtiness": "max", "extra-dirty": False}
            ).model
        self.model["domain"] = "janitor"

        # make rm2 extra dirty
        self.model["nodes"]["rm2"]["unknown"]["dirty"]["actual"] = False
        self.model["nodes"]["rm2"]["unknown"]["extra-dirty"]["actual"] = True

        Observe(zero, "agent1", "rm0").apply(self.model)

        # goal
        goal = create_goal(Point(2, 2), [], [])
        goal["hard-goals"] = [g for g in goal["hard-goals"] if g[1] != "rm4"]
        self.model["goal"] = goal

        # create executors
        wd = join(getcwd(), "../..")
        assert exists(join(wd, "../optic-cplex"))
        central_planner = Planner(ten, working_directory=wd)
        local_planner = Planner(ten, working_directory=wd, domain_file="../janitor/janitor-single-domain.pddl")

        self.agent1_executor = AgentExecutor(agent="agent1", planning_time=ten, planner_id=None)
        self.agent2_executor = AgentExecutor(agent="agent2", planning_time=ten, planner_id=None)
        self.planner_executor = CentralPlannerExecutor(
            agent="planner", planning_time=ten, executor_ids=[self.agent1_executor.id, self.agent2_executor.id],
            agent_names=["agent1", "agent2"], central_planner=central_planner, local_planner=local_planner
        )
        self.agent1_executor.planner_id = self.planner_executor.id
        self.agent2_executor.planner_id = self.planner_executor.id

    def test_quick_full_problem(self):
        # given
        simulator = Simulator(self.model,
                              {"agent1": self.agent1_executor,
                               "agent2": self.agent2_executor,
                               "planner": self.planner_executor
                               })
        # when
        simulator.run()

        # then
        self.assertTrue(simulator.is_goal_in_model())

