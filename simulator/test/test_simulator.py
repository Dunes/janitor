"""
Created on 26 Jun 2014

@author: jack
"""
import unittest
from unittest.mock import MagicMock, Mock, patch, call

from hamcrest import assert_that, contains, is_not, empty, is_, has_length, has_item, equal_to

from decimal import Decimal

import simulator
from action import Move, ExtraClean, Action, Observe, Clean, Stalled
from action_state import ExecutionState, ActionState
from util.builder import ModelBuilder
from queue import PriorityQueue
from planning_exceptions import ExecutionError
from simulator import ExecutionResult


class TestAgents(unittest.TestCase):

    def test_with_not_extra_clean(self):
        # given
        agent = "agent"
        move = Move(None, None, agent, None, None)
        expected = {agent}

        # when
        actual = simulator.agents(move)

        # then
        assert_that(actual, equal_to(expected))

    def test_with_extra_clean(self):
        # given
        agent0 = "agent0"
        agent1 = "agent1"
        extra_clean = ExtraClean(None, None, agent0, agent1, None, None)
        expected = {agent0, agent1}

        # when
        actual = simulator.agents(extra_clean)

        # then
        assert_that(actual, equal_to(expected))

    def test_with_invalid_arg(self):
        # given
        action = None
        # then
        with self.assertRaises(AttributeError):
            # when
            simulator.agents(action)


class TestObserveEnvironment(unittest.TestCase):

    @patch("simulator.Observe.apply", autospec=True)
    def test_with_no_observers(self, apply):
        # given
        apply.return_value = False
        model = ModelBuilder().with_agent("agent", at="node").model
        expected = {}

        # when
        actual = simulator.observe_environment(model)

        # then
        assert_that(actual, equal_to(expected))

    @patch("simulator.Observe.apply", autospec=True)
    def test_with_observer(self, apply):
        # given
        apply.return_Value = True
        model = ModelBuilder().with_agent("agent", at="node").model
        expected = {"agent": "node"}

        # when
        actual = simulator.observe_environment(model)

        # then
        assert_that(actual, equal_to(expected))

    @patch("simulator.Observe.apply", autospec=True)
    def test_with_some_observing_but_not_all(self, apply):
        # given
        apply.side_effect = iter([False, True])
        model = ModelBuilder(ordered=True).with_agent("alice", at="elsewhere") \
            .with_agent("bob", at="node").model
        expected = {"bob": "node"}

        # when
        actual = simulator.observe_environment(model)

        # then
        assert_that(actual, equal_to(expected))


class TestAdjustPlan(unittest.TestCase):

    def test_adds_start_time_to_actions(self):
        # given
        start_time = 0
        duration = 10
        time_to_add = 1
        plan = [Action(start_time, duration)]

        # when
        actual = simulator.adjust_plan(plan, time_to_add)

        # then
        assert_that(actual, contains(Action(start_time + time_to_add, duration)))

    def test_inserts_observe_action(self):
        start_time = 0
        duration = 10
        plan = [Move(start_time, duration, "agent", "start_node", "end_node")]    # when
        actual = simulator.adjust_plan(plan, 0)

        # then
        assert_that(actual, contains(
            Move(start_time, duration, "agent", "start_node", "end_node"),
            Observe(start_time + duration, "agent", "end_node")))


class TestExecutePartialActions(unittest.TestCase):

    def test_calls_partially_apply(self):
        # given
        move = Mock(Move)
        model = Mock(name="model")
        deadline = 0

        # when
        simulator.execute_partial_actions([move], model, deadline)

        # then
        move.partially_apply.assert_called_once_with(model, deadline)

    def test_returns_partial_actions(self):
        # given
        move = Mock(Move)
        model = Mock(name="model")
        deadline = 0
        expected = [move.partially_apply()]

        # when
        actual = simulator.execute_partial_actions([move], model, deadline)

        # then
        assert_that(actual, equal_to(expected))


class TestExecuteActionQueue(unittest.TestCase):

    action_template = Move(None, None, None, None, None)

    def test_does_not_execute_actions_past_deadline(self):
        # given
        action1 = Mock(self.action_template, name="action1")
        action1.apply.return_value = False
        action2 = Mock(self.action_template, name="action2")
        deadline = 10
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put(ActionState(action1, deadline, ExecutionState.executing))
        execution_queue.put(ActionState(action2, deadline+1, ExecutionState.executing))

        # when
        actual, stalled = simulator.execute_action_queue(model, execution_queue,
            break_on_new_knowledge=False, deadline=deadline)

        # then
        assert_that(actual.simulation_time, equal_to(deadline))
        assert_that(actual.executed, contains(action1))
        assert_that(actual.observations, empty())
        assert_that(stalled, equal_to({}))
        action1.apply.assert_called_once_with(model)
        assert_that(is_not(action2.called))

    def test_does_not_execute_actions_of_stalled_agents(self):
        # given
        agent_name = "agent"
        stalled = {agent_name}
        action1 = Mock(self.action_template)
        action1.agent = agent_name
        deadline = 10
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put(ActionState(action1, deadline, ExecutionState.executing))

        # when
        actual, _stalled = simulator.execute_action_queue(model, execution_queue,
            break_on_new_knowledge=False, deadline=deadline, stalled=stalled)

        # then
        assert_that(execution_queue.empty())
        assert_that(actual.executed, is_(empty()))
        assert_that(is_not(action1.apply.called))

    def test_applies_executing_actions(self):
        # given
        action1 = Mock(self.action_template, name="action1")
        action1.apply.return_value = False
        deadline = 10
        end_time = 5
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put(ActionState(action1, end_time, ExecutionState.executing))

        # when
        actual, stalled = simulator.execute_action_queue(model, execution_queue,
            break_on_new_knowledge=False, deadline=deadline)

        # then
        assert_that(actual.simulation_time, equal_to(end_time))
        assert_that(actual.executed, contains(action1))
        assert_that(actual.observations, empty())
        assert_that(stalled, equal_to({}))
        assert_that(execution_queue.empty())
        action1.apply.assert_called_once_with(model)

    def test_applies_concurrently_finishing_actions_when_knowledge(self):
        # given
        observe = MagicMock(Observe(None, None, None))
        observe.apply.return_value = True
        clean = MagicMock(Clean(None, None, None, None))
        clean.apply.return_value = False
        clean.__lt__.return_value = False
        deadline = 10
        model = MagicMock(name="model", autospec=dict)
        execution_queue = PriorityQueue()
        execution_queue.put(ActionState(observe, deadline, ExecutionState.executing))
        execution_queue.put(ActionState(clean, deadline, ExecutionState.executing))

        # when
        actual, stalled = simulator.execute_action_queue(model, execution_queue,
            break_on_new_knowledge=False, deadline=deadline)

        # then
        assert_that(actual.simulation_time, equal_to(deadline))
        assert_that(actual.executed, contains(observe, clean))
        assert_that(actual.observations, contains(observe.end_time))
        assert_that(stalled, equal_to({}))
        observe.apply.assert_called_once_with(model)
        clean.apply.assert_called_once_with(model)

    def test_stalls_agent_when_action_not_applicable(self):
        # given
        agent_name = "agent"
        stalled_time = -1
        action1 = Mock(self.action_template, agent=agent_name, start_time=stalled_time)
        action1.is_applicable.return_value = False
        deadline = 0
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put(ActionState(action1, deadline, ExecutionState.pre_start))

        # when
        actual, stalled = simulator.execute_action_queue(model, execution_queue,
            break_on_new_knowledge=False, deadline=deadline)

        # then
        assert_that(execution_queue.empty())
        assert_that(actual.executed, is_(empty()))
        assert_that(is_not(action1.apply.called))
        assert_that(stalled, contains(agent_name))
        assert_that(stalled, equal_to({agent_name: stalled_time}))

    def test_raises_error_when_stalled_agent_found_but_should_break_on_new_knowledge(self):
        # given
        agent_name = "agent"
        action1 = Mock(self.action_template)
        action1.agent = agent_name
        action1.is_applicable.return_value = False
        end_time = 0
        deadline = 10
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put(ActionState(action1, end_time, ExecutionState.pre_start))

        # when
        with self.assertRaises(ExecutionError):
            simulator.execute_action_queue(model, execution_queue, break_on_new_knowledge=True, deadline=deadline)

        # then
        assert_that(execution_queue.empty())
        assert_that(is_not(action1.apply.called))

    def test_raises_error_when_queue_in_inconsistent_state(self):
        # given
        action1 = Mock(self.action_template)
        action1.is_applicable.return_value = True
        deadline = 0
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put(ActionState(action1, deadline, ExecutionState.finished))

        # when
        with self.assertRaises(ExecutionError):
            simulator.execute_action_queue(model, execution_queue,
                break_on_new_knowledge=True, deadline=deadline)

        # then
        assert_that(execution_queue.empty())
        assert_that(is_not(action1.apply.called))

    # patch needed otherwise getting str or repr of action object produces error because of mocked methods
    @patch("action.Action._format", new=Mock(return_value="Action()"))
    def test_starts_actions_and_adds_back_to_queue(self):
        # given
        start_time = 0
        deadline = 10
        action_to_start = Action(start_time, deadline+1)
        action_to_start.agent = Mock(name="agent")
        action_to_start.is_applicable = Mock(return_val=True)
        action_to_start.apply = Mock(name="apply")
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put(ActionState(action_to_start, start_time, ExecutionState.pre_start))

        # when
        actual, _stalled = simulator.execute_action_queue(model, execution_queue,
            break_on_new_knowledge=False, deadline=deadline)

        # then
        assert_that(execution_queue.queue, has_length(1))
        time, state, action = execution_queue.queue[0]
        assert_that(time, equal_to(action_to_start.end_time))
        assert_that(state, equal_to(ExecutionState.executing))
        assert_that(action, equal_to(action_to_start))
        assert_that(actual.executed, is_(empty()))
        assert_that(is_not(action_to_start.apply.called))
        assert_that(actual.simulation_time, equal_to(start_time))


class TestRunPlan(unittest.TestCase):

    def setUp(self):
        self.patch("simulator.PriorityQueue")
        self.patch("simulator.execute_action_queue")
        self.patch("simulator.execute_partial_actions")
        self.patch("simulator.get_executing_actions")

    def patch(self, name):
        p = patch(name, auto_spec=True)
        mock = p.start()
        self.addCleanup(p.stop)
        setattr(self, name.rsplit(".")[-1], mock)

    def test_creates_priority_queue_correctly(self):
        # given
        self.PriorityQueue().empty.return_value = True
        end_time = 10
        action1 = Mock(end_time=end_time)
        action2 = Mock(end_time=end_time)
        action3 = Mock(end_time=end_time)
        plan = [action1, action2, action3]
        model = Mock(name="model")
        self.execute_action_queue.return_value = (
            ExecutionResult(plan, set(), Mock(name="observation_time")), Mock(name="stalled")
        )

         # when
        simulator.run_plan(model, plan, Mock(name="sim_time"), Mock(name="exec_ext"))

        # then
        put = self.PriorityQueue().put
        assert_that(put.call_count, is_(3))
        put.assert_has_calls([
            call.put(ActionState(action1)),
            call.put(ActionState(action2)),
            call.put(ActionState(action3))
        ])

    def test_returns_if_plan_fully_executed(self):
        # given
        self.PriorityQueue().empty.return_value = True
        action1 = Mock(name="action1")
        action2 = Mock(name="action2")
        action3 = Mock(name="action3")
        plan = [action1, action2, action3]
        model = Mock(name="model")
        observation_time = Mock(name="observation_time")
        self.execute_action_queue.return_value = ExecutionResult(plan, (), observation_time), Mock(name="stalled")

        # when
        actual = simulator.run_plan(model, plan, Mock(name="sim_time"), Mock(name="exec_ext"))

        # then
        assert_that(actual.executed, equal_to(plan))
        assert_that(actual.observations, empty())
        assert_that(actual.simulation_time, equal_to(observation_time))
        self.execute_action_queue.assert_called_once_with(
            model, self.PriorityQueue(), break_on_new_knowledge=True, deadline=float("infinity"))

    def test_executes_actions_during_deadline_extension(self):
        # given
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = []
        end_time = 20
        observation_time, executed_first_pass = 0, [Mock(end_time=end_time-1)]
        observation_whilst_planning = 10
        executed_second_pass = [Mock(end_time=end_time)]
        self.execute_action_queue.side_effect = [
            (ExecutionResult(executed_first_pass, {observation_time}, observation_time), {}),
            (ExecutionResult(executed_second_pass, {observation_whilst_planning}, observation_whilst_planning), {})
        ]
        self.execute_partial_actions.return_value = []
        model = Mock(name="model")
        execution_extension = 100
        plan = executed_first_pass + executed_second_pass

        # when
        actual = simulator.run_plan(model, plan, Mock(name="sim_time"), execution_extension)

        # then
        assert_that(self.execute_action_queue.call_count, is_(2))
        self.execute_action_queue.assert_has_calls([
            call.execute_action_queue(model, self.PriorityQueue(), break_on_new_knowledge=True,
                deadline=Decimal("infinity")),
            call.execute_action_queue(model, self.PriorityQueue(), break_on_new_knowledge=False,
                deadline=observation_time+execution_extension, stalled={})
        ])
        assert_that(actual.executed, equal_to(plan))
        assert_that(actual.observations, contains(observation_time, observation_whilst_planning))
        assert_that(actual.simulation_time, equal_to(end_time))

    def test_reports_initial_observation_time_if_no_obs_whilst_planning(self):
        # given
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = []
        end_time = 20
        observation_time, executed_first_pass = 0, [Mock(end_time=end_time-1)]
        executed_second_pass = [Mock(end_time=end_time)]
        self.execute_action_queue.side_effect = [
            (ExecutionResult(executed_first_pass, {observation_time}, observation_time), {}),
            (ExecutionResult(executed_second_pass, set(), None), {})
        ]
        self.execute_partial_actions.return_value = []
        model = Mock(name="model")
        execution_extension = 100
        plan = executed_first_pass + executed_second_pass    # when
        actual = simulator.run_plan(model, plan, Mock(name="sim_time"), execution_extension)    # then
        assert_that(actual.executed, equal_to(plan))
        assert_that(actual.observations, contains(observation_time))
        assert_that(actual.simulation_time, equal_to(end_time))

    def test_partially_execute_actions_that_are_started(self):
        # given
        end_time = 20
        mid_execution_action = Mock(name="mid_execution", end_time=end_time, start_time=end_time-1)
        pre_start_action = Mock(name="not_started")
        execution_state = [
            ActionState(mid_execution_action, None, ExecutionState.executing),
            ActionState(pre_start_action, None, ExecutionState.pre_start)
        ]
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = tuple(execution_state)
        observation_time = 0
        self.execute_action_queue.side_effect = [
            (ExecutionResult([], {observation_time}, observation_time), {}),
            (ExecutionResult([], set(), None), {})
        ]
        self.execute_partial_actions.return_value = [mid_execution_action]
        model = Mock(name="model")
        execution_extension = 100
        plan = [mid_execution_action, pre_start_action]

        # when
        actual = simulator.run_plan(model, plan, Mock(name="sim_time"), execution_extension)

        # then
        assert_that(actual.executed, contains(mid_execution_action))
        assert_that(actual.observations, contains(observation_time))
        assert_that(actual.simulation_time, equal_to(end_time))
        self.execute_partial_actions.assert_called_once_with(
            self.get_executing_actions.return_value, model, observation_time+execution_extension)

    def test_does_not_partially_execute_actions_that_start_on_deadline(self):
        # given
        observation_time = 0
        execution_extension = 10
        deadline = observation_time + execution_extension
        mid_execution_action = Mock(name="mid_execution", start_time=deadline-1, end_time=deadline+1)
        just_starting_action = Mock(name="just_started", start_time=deadline, end_time=deadline+1)
        execution_state = [
            ActionState(mid_execution_action, observation_time, ExecutionState.executing),
            ActionState(just_starting_action, None, ExecutionState.executing)
        ]
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = tuple(execution_state)
        self.execute_action_queue.side_effect = [
            (ExecutionResult([], {observation_time}, observation_time), {}),
            (ExecutionResult([], set(), None), {})
        ]
        self.execute_partial_actions.return_value = [mid_execution_action]
        model = Mock(name="model")
        plan = [mid_execution_action, just_starting_action]

        # when
        simulator.run_plan(model, plan, Mock(name="sim_time"), execution_extension)

        # then
        self.execute_partial_actions.assert_called_once_with(
            self.get_executing_actions.return_value, model, deadline)

    def test_error_if_mid_execution_action_with_zero_duration(self):
        # given
        mid_execution_action = Mock(name="mid_execution", start_time=0, duration=0)
        execution_state = [ActionState(mid_execution_action, None, ExecutionState.executing)]
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = tuple(execution_state)
        self.execute_action_queue.side_effect = [
            (ExecutionResult([Mock(name="action")], {0}, 0), {}),
            (ExecutionResult([], set(), None), {})
        ]
        model = Mock(name="model")
        execution_extension = 100
        plan = [mid_execution_action]

        # when
        with self.assertRaises(AssertionError):
            simulator.run_plan(model, plan, Mock(name="sim_time"), execution_extension)

    def test_report_observation_whilst_planning(self):
        # given
        observation_time = 0
        observation_whilst_planning = 10
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = []
        self.execute_action_queue.side_effect = [
            (ExecutionResult([Mock(name="action", end_time=0)], {observation_time}, observation_time), {}),
            (ExecutionResult([], {observation_whilst_planning}, observation_whilst_planning), {})
        ]
        self.execute_partial_actions.return_value = []
        model = Mock(name="model")
        plan = []
        execution_extension = 100

        # when
        actual = simulator.run_plan(model, plan, Mock(name="sim_time"), execution_extension)

        # then
        assert_that(actual.observations, contains(observation_time, observation_whilst_planning))

    def test_report_no_observation_whilst_planning(self):
        # given
        observation_time = 0
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = []
        self.execute_action_queue.side_effect = [
            (ExecutionResult([Mock(name="action", end_time=0)], {observation_time}, observation_time), {}),
            (ExecutionResult([], set(), None), {})
        ]
        self.execute_partial_actions.return_value = []
        model = Mock(name="model")
        plan = []
        execution_extension = 100

        # when
        actual = simulator.run_plan(model, plan, Mock(name="sim_time"), execution_extension)

        # then
        assert_that(actual.observations, contains(observation_time))

    def test_add_stalled_actions_when_agent_stalled_in_initial_pass(self):
        # given
        name = "agent"
        stalled_time = 0
        stalled = {name: stalled_time}
        observation_time = 10
        execution_extension = 10
        deadline = observation_time + execution_extension
        previous_action = Mock(name="previous-action", agent=name, end_time=stalled_time)
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = []
        self.execute_action_queue.side_effect = [
            (ExecutionResult([previous_action], {observation_time}, observation_time), stalled),
            (ExecutionResult([], set(), None), stalled)
        ]
        self.execute_partial_actions.return_value = []
        plan = []

        # when
        actual = simulator.run_plan(Mock(name="model"), plan, Mock(name="sim_time"), execution_extension)

        # then
        assert_that(actual.executed, has_item(Stalled(previous_action.end_time, deadline, name)))

    def test_add_stalled_action_when_no_previous_action(self):
        # given
        name = "agent"
        stalled_time = 0
        stalled = {name: stalled_time}
        observation_time = 10
        execution_extension = 10
        deadline = observation_time + execution_extension
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = []
        self.execute_action_queue.side_effect = [
            (ExecutionResult([Mock(name="other-action", end_time=execution_extension)],
                {observation_time}, observation_time), stalled),
            (ExecutionResult([], set(), None), stalled)
        ]
        self.execute_partial_actions.return_value = []
        plan = []

        # when
        actual = simulator.run_plan(Mock(name="model"), plan, Mock(name="sim_time"), execution_extension)

        # then
        assert_that(actual.executed, has_item(Stalled(stalled_time, deadline, name)))

    def test_add_stalled_action_in_second_pass(self):
        # given
        name = "agent"
        stalled_time = 0
        stalled = {name: stalled_time}
        observation_time = 10
        execution_extension = 10
        deadline = observation_time + execution_extension
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = []
        self.execute_action_queue.side_effect = [
            (ExecutionResult([], {observation_time}, observation_time), {}),
            (ExecutionResult([Mock(name="other-action", end_time=execution_extension)], set(), None), stalled),
        ]
        self.execute_partial_actions.return_value = []
        plan = []

        # when
        actual = simulator.run_plan(Mock(name="model"), plan, Mock(name="sim_time"), execution_extension)

        # then
        assert_that(actual.executed, has_item(Stalled(stalled_time, deadline, name)))


class TestGetExecutingActions(unittest.TestCase):

    def test_gets_executing_actions(self):
        # given
        deadline = 0
        time = deadline - 1
        action = Mock(name="action", start_time=time)
        action_state = [ActionState(action, time=time, state=ExecutionState.executing)]    # when
        actual = simulator.get_executing_actions(action_state, deadline)    # then
        assert_that(actual, contains(action))

    def test_does_not_get_not_executing_actions(self):
        # given
        deadline = 0
        time = deadline - 1
        pre_start = Mock(name="pre_start", start_time=time)
        finished = Mock(name="finished", start_time=time)
        action_states = [
            ActionState(pre_start, time=time, state=ExecutionState.pre_start),
            ActionState(finished, time=time, state=ExecutionState.finished)]

        # when
        actual = simulator.get_executing_actions(action_states, deadline)

        # then
        assert_that(actual, empty())

    def test_does_not_get_actions_that_start_at_or_after_deadline(self):
        # given
        deadline = 0
        time = deadline
        action = Mock(name="action", start_time=time)
        action_state = [ActionState(action, time=time, state=ExecutionState.executing)]

        # when
        actual = simulator.get_executing_actions(action_state, deadline)

        # then
        assert_that(actual, empty())


class TestRunSimulation(unittest.TestCase):
    pass

if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()