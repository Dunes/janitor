from unittest import TestCase
from unittest.mock import patch, Mock
from hamcrest import assert_that, equal_to, contains_inanyorder, has_length

from operator import attrgetter
from decimal import Decimal

from util.roborescue.builder import ModelBuilder

from roborescue.executor import TaskAllocatorExecutor, AgentExecutor, MedicExecutor, CIVILIAN_VALUE
from roborescue.goal import Goal, Task, Bid
from roborescue.action import Move


class TestTaskAllocatorExecutor(TestCase):

    @patch.object(TaskAllocatorExecutor, "EXECUTORS", new_callable=dict)
    def test__executors(self, executor_cache):
        # given
        ids = [next(TaskAllocatorExecutor.ID_COUNTER) for _ in range(3)]
        names = list("abc")
        executor_cache.update(zip(ids, names))
        executor = TaskAllocatorExecutor(agent="allocator", planning_time=None, executor_ids=ids,
            agent_names=names, central_planner=None, local_planner=None, event_executor=None)

        # then
        assert_that(list(executor._executors), contains_inanyorder(*names))

    @patch.object(TaskAllocatorExecutor, "EXECUTORS", new_callable=dict)
    def test_executor_by_name(self, executor_cache):
        # given
        ids = [next(TaskAllocatorExecutor.ID_COUNTER) for _ in range(3)]
        names = list("abc")
        executors = list("xyz")
        executor_cache.update(zip(ids, executors))
        e = TaskAllocatorExecutor(agent="allocator", planning_time=None, executor_ids=ids,
            agent_names=names, central_planner=None, local_planner=None, event_executor=None)

        # then
        for name, executor in zip(names, executors):
            with self.subTest(name=name, executor=executor):
                assert_that(e.executor_by_name(name), equal_to(executor))


class TestTaskAllocatorExecutorComputeAllocation(TestCase):

    def set_up_executors(self, num_executors):
        ids = range(num_executors)
        names = [chr(ord("A") + i) for i in ids]
        executors = [Mock(autospec=AgentExecutor, id=i, agent=name) for i, name in zip(ids, names)]

        allocator = TaskAllocatorExecutor(agent="allocator", planning_time=None, executor_ids=ids,
            agent_names=names, central_planner=None, local_planner=None, event_executor=None)
        allocator.id = -1
        TaskAllocatorExecutor.EXECUTORS.update((e.id, e) for e in executors + [allocator])

        return allocator, executors

    def test_allocate_goals_in_deadline_order(self):
        # given
        allocator, (executor,) = self.set_up_executors(1)
        tasks = [Task(Goal(predicate="a", deadline=1), 0), Task(Goal(predicate="b", deadline=0), 0)]
        bids = {t: Bid(agent=executor.agent, value=0, task=t, requirements=(), computation_time=0) for t in tasks}
        executor.generate_bid.side_effect = lambda task, planner, model, time, events: bids[task]

        # when
        allocation, _ = allocator.compute_allocation(tasks, None, None)

        # then
        assert_that(allocation, equal_to(sorted(bids.values(), key=attrgetter("task.goal.deadline"))))

    def test_merge_duplicated_tasks(self):
        # given
        allocator, (executor,) = self.set_up_executors(1)
        tasks = [Task(Goal(predicate="a", deadline=0), 1)] * 2
        summed_tasks = Task.combine(tasks)
        bid = Bid(agent=executor.agent, value=0, task=summed_tasks, requirements=(), computation_time=0)
        bids = {summed_tasks: bid}
        executor.generate_bid.side_effect = lambda task, planner, model, time, events: bids[task]

        # when
        allocation, _ = allocator.compute_allocation(tasks, None, None)

        # then
        assert_that(allocation, equal_to([bid]))

    def test_merge_duplicated_tasks_with_different_value(self):
        # given
        allocator, (executor,) = self.set_up_executors(1)
        goal = Goal(predicate="a", deadline=0)
        tasks = [Task(goal, 0), Task(goal, 1)]
        summed_tasks = Task.combine(tasks)
        bid = Bid(agent=executor.agent, value=0, task=summed_tasks, requirements=(), computation_time=0)
        bids = {summed_tasks: bid}
        executor.generate_bid.side_effect = lambda task, planner, model, time, events: bids[task]

        # when
        allocation, _ = allocator.compute_allocation(tasks, None, None)

        # then
        assert_that(allocation, equal_to([bid]))

    def test_no_merge_tasks_with_same_deadlines(self):
        # given
        allocator, (executor,) = self.set_up_executors(1)
        tasks = [Task(Goal(predicate="a", deadline=0), 1), Task(Goal(predicate="b", deadline=0), 1)]
        bids = {t: Bid(agent=executor.agent, value=0, task=t, requirements=(), computation_time=0) for t in tasks}
        executor.generate_bid.side_effect = lambda task, planner, model, time, events: bids[task]

        # when
        allocation, _ = allocator.compute_allocation(tasks, None, None)

        # then
        assert_that(allocation, equal_to(sorted(bids.values(), key=attrgetter("task.goal.deadline"))))

    def test_merge_some_tasks_with_same_deadlines(self):
        # given
        allocator, (executor,) = self.set_up_executors(1)
        tasks = [Task(Goal(predicate="a", deadline=0), 1),
                 Task(Goal(predicate="b", deadline=0), 1),
                 Task(Goal(predicate="a", deadline=0), 1)]
        a_tasks = Task.combine([tasks[0], tasks[2]])
        b_task = tasks[1]
        bids = {
            a_tasks: Bid(agent=executor.agent, value=0, task=a_tasks, requirements=(), computation_time=0),
            b_task: Bid(agent=executor.agent, value=0, task=b_task, requirements=(), computation_time=0)
        }
        executor.generate_bid.side_effect = lambda task, planner, model, time, events: bids[task]

        # when
        allocation, _ = allocator.compute_allocation(tasks, None, None)

        # then
        assert_that(allocation, has_length(2))
        assert_that(set(allocation), equal_to(set(bids.values())))
        assert_that([b.task.goal.deadline for b in allocation],
                    equal_to(sorted([b.task.goal.deadline for b in bids.values()])))

    def test_allocates_sub_tasks(self):
        # given
        allocator, (executor,) = self.set_up_executors(1)
        primary_task = Task(Goal(predicate="a", deadline=0), 0)
        secondary_task = Task(Goal(predicate="b", deadline=1), 0)
        bids = {
            primary_task: Bid(agent=executor.agent, value=0, task=primary_task, requirements=[secondary_task],
                              computation_time=0),
            secondary_task: Bid(agent=executor.agent, value=0, task=secondary_task, requirements=(), computation_time=0)
        }
        executor.generate_bid.side_effect = lambda task, planner, model, time, events: bids[task]

        # when
        allocation, _ = allocator.compute_allocation([primary_task], None, None)

        # then
        assert_that(allocation, equal_to(sorted(bids.values(), key=attrgetter("task.goal.deadline"))))

    def test_merge_same_tasks_when_added_later(self):
        # given
        allocator, (executor,) = self.set_up_executors(1)
        needed_twice_task = Task(Goal(predicate="a", deadline=0), 1)
        requiring_task = Task(Goal(predicate="b", deadline=1), 1)
        tasks = [needed_twice_task, requiring_task]

        needed_twice_bid = Bid(agent=executor.agent, value=0, task=needed_twice_task, requirements=(),
                               computation_time=0)
        requiring_bid = Bid(agent=executor.agent, value=0, task=requiring_task, requirements=[needed_twice_task],
                             computation_time=0)
        executor.generate_bid.side_effect = [needed_twice_bid, requiring_bid]

        # when
        allocation, _ = allocator.compute_allocation(tasks, None, None)

        # then
        modified_bid = needed_twice_bid._replace(task=Task.combine([needed_twice_task] * 2))
        assert_that(allocation, equal_to([modified_bid, requiring_bid]))

    def test_assigns_goals_to_best_bidder(self):
        # given
        allocator, executors = self.set_up_executors(2)
        task = Task(Goal(predicate="a", deadline=0), 0)
        bids = [Bid(agent=e.agent, value=e.id * 10, task=task, requirements=(), computation_time=0) for e in executors]
        executors[0].generate_bid.return_value = bids[0]
        executors[1].generate_bid.return_value = bids[1]

        # when
        allocation, _ = allocator.compute_allocation([task], None, None)

        # then
        assert_that(allocation, equal_to([max(bids, key=attrgetter("value"))]))

    def test_compute_computation_time(self):
        # given
        allocator, executors = self.set_up_executors(2)
        task = Task(Goal(predicate="a", deadline=0), 0)
        bids = [Bid(agent=e.agent, value=0, task=task, requirements=(), computation_time=e.id * 10) for e in executors]
        executors[0].generate_bid.return_value = bids[0]
        executors[1].generate_bid.return_value = bids[1]

        # when
        _, time_taken = allocator.compute_allocation([task], None, None)

        # then
        assert_that(time_taken, equal_to(max(b.computation_time for b in bids)))


class TestMedicGenerateBid(TestCase):

    def test_basic(self):
        # given
        medic = MedicExecutor(agent="medic", planning_time=0)
        goal = Goal(predicate=("rescued", "civ0"), deadline=Decimal("Infinity"))
        task = Task(goal=goal, value=Decimal(1))

        model = ModelBuilder().with_edge("a", "b").model
        plan = []
        time_taken = 1
        planner = Mock(**{"get_plan_and_time_taken.side_effect": [[plan, time_taken]]})

        # when
        bid = medic.generate_bid(task, planner, model, None, None)

        # then
        assert_that(bid.agent, equal_to("medic"))
        assert_that(bid.task, equal_to(task))
        assert_that(bid.computation_time, equal_to(time_taken))
        assert_that(bid.value, equal_to(CIVILIAN_VALUE))
        assert_that(bid.requirements, equal_to(()))

    def test_generate_correct_requirements_from_plan(self):
        # given
        medic = MedicExecutor(agent="medic", planning_time=0)
        goal = Goal(predicate=("rescued", "civ0"), deadline=Decimal("Infinity"))
        task = Task(goal=goal, value=Decimal(1))

        model = ModelBuilder().with_edge("a", "b", blockedness=1).model
        start_time = 0
        plan = [Move(start_time, 1, "medic", "a", "b")]
        time_taken = 1
        planner = Mock(**{"get_plan_and_time_taken.side_effect": [[plan, time_taken]]})

        # when
        bid = medic.generate_bid(task, planner, model, None, None)

        # then
        assert_that(bid.agent, equal_to("medic"))
        assert_that(bid.task, equal_to(task))
        assert_that(bid.computation_time, equal_to(time_taken))
        assert_that(bid.value, equal_to(CIVILIAN_VALUE))
        expected_requirement = Task(goal=Goal(predicate=("edge", "a", "b"), deadline=start_time), value=CIVILIAN_VALUE)
        assert_that(bid.requirements, equal_to((expected_requirement,)))
