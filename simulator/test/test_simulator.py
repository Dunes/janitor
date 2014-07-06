'''
Created on 26 Jun 2014

@author: jack
'''
import unittest
from unittest.mock import MagicMock, Mock, patch, call

from hamcrest import assert_that, contains, is_not, empty, is_, has_length
from util.matchers.actionmatcher import equal_to  # @UnresolvedImport

import simulator
from action import Move, ExtraClean, Action, Observe, ExecutionState, Clean
from util.builder import ActionBuilder, ModelBuilder
from util.accuracy import quantize
from queue import PriorityQueue
from planning_exceptions import ExecutionError

class TestAgents(unittest.TestCase):

    def test_with_not_extra_clean(self):
        # given
        agent = "agent"
        move = Move(None, None, agent, None, None)
        expected = set((agent,))

        # when
        actual = simulator.agents(move)

        self.assertEqual(expected, actual)

    def test_with_extra_clean(self):
        # given
        agent0 = "agent0"
        agent1 = "agent1"
        extra_clean = ExtraClean(None, None, agent0, agent1, None, None)
        expected = set((agent0, agent1))

        # when
        actual = simulator.agents(extra_clean)

        self.assertEqual(expected, actual)

    def test_with_invalid_arg(self):
        # given
        action = None

        # then
        with self.assertRaises(AttributeError):
            # when
            simulator.agents(action)


class TestGetLatestObservationTime(unittest.TestCase):

    def test_only_report_move_end_time(self):
        # given
        action_builder = ActionBuilder().agent().end_node()
        executed = [action_builder.end_time(0).clean(),
                    action_builder.end_time(1).move(),
                    action_builder.end_time(2).clean()]
        observers = {"agent": "end_node"}
        expected = quantize(1)

        # when
        actual = simulator.get_latest_observation_time(observers, executed)

        # then
        self.assertEqual(expected, actual)

    def test_report_latest_move(self):
        # given
        action_builder = ActionBuilder().agent().end_node()
        executed = [action_builder.end_time(0).move(),
                    action_builder.end_time(1).move()]
        observers = {"agent": "end_node"}
        expected = quantize(1)

        # when
        actual = simulator.get_latest_observation_time(observers, executed)

        # then
        self.assertEqual(expected, actual)

    def test_report_latest_move_reverse_order(self):
        # given
        action_builder = ActionBuilder().agent().end_node()
        executed = [action_builder.end_time(1).move(),
                    action_builder.end_time(0).move()]
        observers = {"agent": "end_node"}
        expected = quantize(1)

        # when
        actual = simulator.get_latest_observation_time(observers, executed)

        # then
        self.assertEqual(expected, actual)

    def test_only_report_move_with_observer(self):
        # given
        action_builder = ActionBuilder()
        executed = [action_builder.agent("observer").end_node("here").end_time(0).move(),
                    action_builder.agent("other").end_node("elsewhere").end_time(1).move()]
        observers = {"observer": "here"}
        expected = quantize(0)

        # when
        actual = simulator.get_latest_observation_time(observers, executed)

        # then
        self.assertEqual(expected, actual)

    def test_report_none_if_no_observers(self):
        # given
        observers = {}
        executed = [ActionBuilder().agent().end_time().end_node().move()]
        expected = None

        # when
        actual = simulator.get_latest_observation_time(observers, executed)

        # then
        self.assertEqual(expected, actual)



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
        self.assertEqual(expected, actual)


    @patch("simulator.Observe.apply", autospec=True)
    def test_with_observer(self, apply):
        # given
        apply.return_Value = True
        model = ModelBuilder().with_agent("agent", at="node").model
        expected = {"agent": "node"}

        # when
        actual = simulator.observe_environment(model)

        # then
        self.assertEqual(expected, actual)

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
        self.assertEqual(expected, actual)


class TestRemoveUnusedTempNodes(unittest.TestCase):

    def test_remove_nodes_starting_with_temp(self):
        # given
        model = ModelBuilder().with_node("temp_node").model
        expected = {}

        # when
        simulator.remove_unused_temp_nodes(model)
        actual = model["nodes"]

        # then
        self.assertDictEqual(expected, actual)

    def test_only_remove_temp_nodes(self):
        # given
        model = ModelBuilder().with_node("temp_node").with_node("node", value="value").model
        expected = {"node": "value"}

        # when
        simulator.remove_unused_temp_nodes(model)
        actual = model["nodes"]

        # then
        self.assertDictEqual(expected, actual)

    def test_does_not_remove_occupied_temp_nodes(self):
        # given
        model = ModelBuilder().with_agent("agent", at="temp_node") \
                .with_node("temp_node", value="value").model
        expected = {"temp_node": "value"}

        # when
        simulator.remove_unused_temp_nodes(model)
        actual = model["nodes"]

        # then
        self.assertDictEqual(expected, actual)

    def test_removes_edges(self):
        # given
        model = ModelBuilder().with_edge("temp_node1", "n1", 1) \
                .with_edge("temp_node2", "n2", 1).with_agent("agent", at="temp_node1").model
        expected = [["temp_node1", "n1", 1]]

        # when
        simulator.remove_unused_temp_nodes(model)
        actual = model["graph"]["edges"]

        # then
        self.assertListEqual(expected, actual)


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
        assert_that(actual, contains(
                equal_to(Action(start_time+time_to_add, duration))))

    def test_inserts_observe_action(self):
        start_time = 0
        duration = 10
        plan = [Move(start_time, duration, "agent", "start_node", "end_node")]

        # when
        actual = simulator.adjust_plan(plan, 0)

        # then
        assert_that(actual, contains(
                equal_to(Move(start_time, duration, "agent", "start_node", "end_node")),
                equal_to(Observe(start_time+duration, "agent", "end_node"))))

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
        self.assertListEqual(expected, actual)

class TestExecuteActionQueue(unittest.TestCase):

    action_template = Move(None, None, None, None, None)

    def test_does_not_execute_actions_past_deadline(self):
        # given
        action1 = Mock(self.action_template)
        action1.apply.return_value = False
        action1.execution_state = ExecutionState.executing
        action2 = Mock(self.action_template)
        deadline = 10
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put((deadline, ExecutionState.executing, action1))
        execution_queue.put((deadline+1, ExecutionState.executing, action2))

        # when
        actual = simulator.execute_action_queue(model, execution_queue, False, deadline)
        simulation_time, executed, stalled = actual

        # then
        assert_that(simulation_time, equal_to(deadline))
        assert_that(executed, contains(equal_to(action1)))
        assert_that(stalled, equal_to(set()))

        action1.apply.assert_called_once_with(model)
        assert_that(is_not(action2.called))

    def test_does_not_execute_actions_of_stalled_agents(self):
        # given
        agent_name = "agent"
        stalled = set([agent_name])
        action1 = Mock(self.action_template)
        action1.agent = agent_name
        deadline = 10
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put((deadline, ExecutionState.executing, action1))

        # when
        actual = simulator.execute_action_queue(model, execution_queue, False,
                deadline, stalled=stalled)
        _simulation_time, executed, _stalled = actual

        # then
        assert_that(execution_queue.empty())
        assert_that(executed, is_(empty()))
        assert_that(is_not(action1.apply.called))

    def test_applies_executing_actions(self):
        # given
        action1 = Mock(self.action_template)
        action1.execution_state = ExecutionState.executing
        deadline = 10
        end_time = 5
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put((end_time, ExecutionState.executing, action1))

        # when
        actual = simulator.execute_action_queue(model, execution_queue, False, deadline)
        simulation_time, executed, stalled = actual

        # then
        assert_that(simulation_time, equal_to(end_time))
        assert_that(executed, contains(equal_to(action1)))
        assert_that(stalled, equal_to(set()))
        assert_that(execution_queue.empty())

        action1.apply.assert_called_once_with(model)

    def test_applies_concurrently_finishing_actions_when_knowledge(self):
        # given
        action1 = MagicMock(self.action_template)
        action1.apply.return_value = True
        action1.execution_state = ExecutionState.executing

        action2 = MagicMock(Clean(None, None, None, None))
        action2.apply.return_value = False
        action2.execution_state = ExecutionState.executing
        action2.__lt__.return_value = False # comes after Move mock

        deadline = 10
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put((deadline, ExecutionState.executing, action1))
        execution_queue.put((deadline, ExecutionState.executing, action2))

        # when
        actual = simulator.execute_action_queue(model, execution_queue, False, deadline)
        simulation_time, executed, stalled = actual

        # then
        assert_that(simulation_time, equal_to(deadline))
        assert_that(executed, contains(equal_to(action1), equal_to(action2)))
        assert_that(stalled, equal_to(set()))

        action1.apply.assert_called_once_with(model)
        action2.apply.assert_called_once_with(model)


    def test_stalls_agent_when_action_not_applicable(self):
        # given
        agent_name = "agent"
        action1 = Mock(self.action_template)
        action1.agent = agent_name
        action1.is_applicable.return_value = False
        deadline = 0
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put((deadline, ExecutionState.executing, action1))

        # when
        actual = simulator.execute_action_queue(model, execution_queue, False, deadline)
        _simulation_time, executed, stalled = actual

        # then
        assert_that(execution_queue.empty())
        assert_that(executed, is_(empty()))
        assert_that(is_not(action1.apply.called))
        assert_that(stalled, contains(agent_name))

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
        execution_queue.put((end_time, ExecutionState.executing, action1))

        # when
        with self.assertRaises(ExecutionError):
            simulator.execute_action_queue(model, execution_queue, True, deadline)

        # then
        assert_that(execution_queue.empty())
        assert_that(is_not(action1.apply.called))

    def test_raises_error_when_queue_in_inconsistent_state(self):
        # given
        action1 = Mock(self.action_template)
        action1.is_applicable.return_value = True
        action1.execution_state = ExecutionState.finished
        deadline = 0
        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put((deadline, ExecutionState.finished, action1))

        # when
        with self.assertRaises(ExecutionError):
            simulator.execute_action_queue(model, execution_queue, True, deadline)

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
        action_to_start.agent = Mock()
        action_to_start.is_applicable = Mock(return_val=True)
        action_to_start.apply = Mock()

        model = Mock(name="model")
        execution_queue = PriorityQueue()
        execution_queue.put((start_time, ExecutionState.pre_start, action_to_start))

        # when
        actual = simulator.execute_action_queue(model, execution_queue, False, deadline)
        simulation_time, executed, _stalled = actual

        # then
        assert_that(execution_queue.queue, has_length(1))
        time, state, action = execution_queue.queue[0]
        assert_that(time, equal_to(action_to_start.end_time))
        assert_that(state, equal_to(ExecutionState.executing))
        assert_that(action, equal_to(action_to_start))
        assert_that(executed, is_(empty()))
        assert_that(is_not(action_to_start.apply.called))
        assert_that(action_to_start.execution_state, equal_to(ExecutionState.executing))
        assert_that(simulation_time, equal_to(start_time))

class TestRunPlan(unittest.TestCase):

    def setUp(self):
        self.patch("simulator.PriorityQueue")
        self.patch("simulator.execute_action_queue")
        self.patch("simulator.execute_partial_actions")
        self.patch("simulator.remove_unused_temp_nodes")

    def patch(self, name):
        p = patch(name)
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
        self.execute_action_queue.return_value = (Mock("observation_time"),
                                                  plan, Mock("stalled"))

        # when
        simulator.run_plan(model, plan, Mock())

        # then
        put = self.PriorityQueue().put
        assert_that(put.call_count, is_(3))
        put.assert_has_calls([
            call.put((action1.start_time, action1.execution_state, action1)),
            call.put((action2.start_time, action2.execution_state, action2)),
            call.put((action3.start_time, action3.execution_state, action3))
        ])

    def test_returns_if_plan_fully_executed(self):
        # given
        self.PriorityQueue().empty.return_value = True
        end_time = 1
        action1 = Mock(end_time=end_time-1)
        action2 = Mock(end_time=end_time)
        action3 = Mock(end_time=end_time-1)
        plan = [action1, action2, action3]
        model = Mock(name="model")
        observation_time = Mock()
        self.execute_action_queue.return_value = (observation_time, plan, Mock("stalled"))

        # when
        actual = simulator.run_plan(model, plan, Mock())

        # then
        assert_that(actual.executed_actions, equal_to(plan))
        assert_that(actual.planning_start, equal_to(observation_time))
        assert_that(actual.simulation_time, equal_to(end_time))
        self.execute_action_queue.assert_called_once_with(
                model, self.PriorityQueue(), break_on_new_knowledge=True,
                deadline=float("infinity"))

    def test_executes_actions_during_deadline_extension(self):
        # given
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = []
        end_time = 20
        observation_time, executed_first_pass, stalled = 0, [Mock(end_time=end_time-1)], Mock()
        observation_whilst_planning = 10
        executed_second_pass = [Mock(end_time=end_time)]
        self.execute_action_queue.side_effect = [
            (observation_time, executed_first_pass, stalled),
            (observation_whilst_planning, executed_second_pass, None)
        ]
        self.execute_partial_actions.return_value = []
        model = Mock(name="model")
        execution_extension = 100
        plan = executed_first_pass + executed_second_pass

        # when
        actual = simulator.run_plan(model, plan, execution_extension)

        # then
        assert_that(self.execute_action_queue.call_count, is_(2))
        self.execute_action_queue.assert_has_calls([
            call.execute_action_queue(model, self.PriorityQueue(), break_on_new_knowledge=True,
                    deadline=float("infinity")),
            call.execute_action_queue(model, self.PriorityQueue(), break_on_new_knowledge=False,
                    deadline=observation_time+execution_extension,
                    execute_partial_actions=self.execute_partial_actions, stalled=stalled)
        ])
        assert_that(actual.executed_actions, equal_to(plan))
        assert_that(actual.planning_start, equal_to(observation_whilst_planning))
        assert_that(actual.simulation_time, equal_to(end_time))

    def test_reports_inital_observation_time_if_no_obs_whilst_planning(self):
        # given
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = []
        end_time = 20
        observation_time, executed_first_pass, stalled = 0, [Mock(end_time=end_time-1)], Mock()
        executed_second_pass = [Mock(end_time=end_time)]
        self.execute_action_queue.side_effect = [
            (observation_time, executed_first_pass, stalled),
            (None, executed_second_pass, None)
        ]
        self.execute_partial_actions.return_value = []
        model = Mock(name="model")
        execution_extension = 100
        plan = executed_first_pass + executed_second_pass

        # when
        actual = simulator.run_plan(model, plan, execution_extension)

        # then
        assert_that(actual.executed_actions, equal_to(plan))
        assert_that(actual.planning_start, equal_to(observation_time))
        assert_that(actual.simulation_time, equal_to(end_time))

    def test_partially_execute_actions_that_are_started(self):
        # given
        end_time = 20
        mid_execution_action = Mock(name="mid_execution", end_time=end_time, start_time=end_time-1)
        pre_start_action = Mock(name="not_started")
        execution_state = [
            (None, ExecutionState.executing, mid_execution_action),
            (None, ExecutionState.pre_start, pre_start_action)
        ]
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = tuple(execution_state)
        observation_time = 0
        self.execute_action_queue.side_effect = [
            (observation_time, [], Mock()),
            (None, [], None)
        ]
        self.execute_partial_actions.return_value = [mid_execution_action]
        model = Mock(name="model")
        execution_extension = 100
        plan = [mid_execution_action, pre_start_action]

        # when
        actual = simulator.run_plan(model, plan, execution_extension)

        # then
        assert_that(actual.executed_actions, contains(mid_execution_action))
        assert_that(actual.planning_start, equal_to(observation_time))
        assert_that(actual.simulation_time, equal_to(end_time))

        self.execute_partial_actions.assert_called_once_with([mid_execution_action],
                model, observation_time+execution_extension)

    def test_does_not_partially_execute_actions_that_start_on_deadline(self):
        # given
        observation_time = 0
        execution_extension = 10
        deadline = observation_time + execution_extension
        mid_execution_action = Mock(name="mid_execution",
                start_time=deadline-1, end_time=deadline+1)
        just_starting_action = Mock(name="just_started",
                start_time=deadline, end_time=deadline+1)
        execution_state = [
            (observation_time, ExecutionState.executing, mid_execution_action),
            (None, ExecutionState.executing, just_starting_action)
        ]
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = tuple(execution_state)
        self.execute_action_queue.side_effect = [
            (observation_time, [], Mock()),
            (None, [], None)
        ]
        self.execute_partial_actions.return_value = [mid_execution_action]
        model = Mock(name="model")
        plan = [mid_execution_action, just_starting_action]

        # when
        simulator.run_plan(model, plan, execution_extension)

        # then
        self.execute_partial_actions.assert_called_once_with([mid_execution_action],
                model, deadline)

    def test_error_if_mid_excution_action_with_zero_duration(self):
        # given
        mid_execution_action = Mock(name="mid_execution", start_time=0, duration=0)
        execution_state = [(None, ExecutionState.executing, mid_execution_action)]
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = tuple(execution_state)
        self.execute_action_queue.side_effect = [
            (0, [], Mock()),
            (None, [], None)
        ]
        model = Mock(name="model")
        execution_extension = 100
        plan = [mid_execution_action]

        # when
        with self.assertRaises(AssertionError):
            simulator.run_plan(model, plan, execution_extension)

    def test_remove_unused_temp_nodes_after_plan_execution(self):
        # given
        self.PriorityQueue().empty.return_value = False
        self.PriorityQueue().queue = []
        self.execute_action_queue.return_value = 0, [Mock(end_time=0)], None
        self.execute_partial_actions.return_value = []
        model = Mock(name="model")

        # when
        simulator.run_plan(model, [], 0)

        # then
        self.remove_unused_temp_nodes.assert_called_once_with(model)

class TestRunSimulation(unittest.TestCase):
    pass

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()