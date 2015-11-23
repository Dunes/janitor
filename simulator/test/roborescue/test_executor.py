from unittest import TestCase
from unittest.mock import patch, Mock
from hamcrest import assert_that, equal_to, contains_inanyorder

from operator import attrgetter

from roborescue.executor import TaskAllocatorExecutor, AgentExecutor
from roborescue.goal import Goal, Bid


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
        goals = [Goal(predicate="a", deadline=1), Goal(predicate="b", deadline=0)]
        bids = {g: Bid(name=executor.agent, value=0, goal=g, requirements=(), computation_time=0) for g in goals}
        executor.generate_bid.side_effect = bids.__getitem__

        # when
        allocation, _ = allocator.compute_allocation(goals)

        # then
        assert_that(allocation, equal_to(sorted(bids.values(), key=attrgetter("goal.deadline"))))

    def test_ignore_duplicated_goals(self):
        # given
        allocator, (executor,) = self.set_up_executors(1)
        goals = first_goal, second_goal = [Goal(predicate="a", deadline=0), Goal(predicate="a", deadline=1)]
        bids = {g: Bid(name=executor.agent, value=0, goal=g, requirements=(), computation_time=0) for g in goals}
        executor.generate_bid.side_effect = bids.__getitem__

        # when
        allocation, _ = allocator.compute_allocation(goals)

        # then
        assert_that(allocation, equal_to([bids[first_goal]]))

    def test_allocates_sub_tasks(self):
        # given
        allocator, (executor,) = self.set_up_executors(1)
        primary_goal, secondary_goal = [Goal(predicate="a", deadline=0), Goal(predicate="b", deadline=1)]
        bids = {
            primary_goal: Bid(name=executor.agent, value=0, goal=primary_goal, requirements=(secondary_goal,),
                              computation_time=0),
            secondary_goal: Bid(name=executor.agent, value=0, goal=secondary_goal, requirements=(), computation_time=0)
        }
        executor.generate_bid.side_effect = bids.__getitem__

        # when
        allocation, _ = allocator.compute_allocation([primary_goal])

        # then
        assert_that(allocation, equal_to(sorted(bids.values(), key=attrgetter("goal.deadline"))))

    def test_reconisder_task_if_earlier_deadline(self):
        # given
        allocator, (executor,) = self.set_up_executors(1)
        primary_goal, secondary_goal = [Goal(predicate="a", deadline=1), Goal(predicate="a", deadline=0)]
        bids = {
            primary_goal: Bid(name=executor.agent, value=0, goal=primary_goal, requirements=(secondary_goal,),
                              computation_time=0),
            secondary_goal: Bid(name=executor.agent, value=0, goal=secondary_goal, requirements=(), computation_time=0)
        }
        executor.generate_bid.side_effect = bids.__getitem__

        # when
        allocation, _ = allocator.compute_allocation([primary_goal])

        # then
        assert_that(allocation, equal_to([bids[secondary_goal]]))

    def test_assigns_goals_to_best_bidder(self):
        # given
        allocator, executors = self.set_up_executors(2)
        goal = Goal(predicate="a", deadline=0)
        bids = [Bid(name=e.agent, value=e.id * 10, goal=goal, requirements=(), computation_time=0) for e in executors]
        executors[0].generate_bid.return_value = bids[0]
        executors[1].generate_bid.return_value = bids[1]

        # when
        allocation, _ = allocator.compute_allocation([goal])

        # then
        assert_that(allocation, equal_to([max(bids, key=attrgetter("value"))]))

    def test_compute_computation_time(self):
        # given
        allocator, executors = self.set_up_executors(2)
        goal = Goal(predicate="a", deadline=0)
        bids = [Bid(name=e.agent, value=0, goal=goal, requirements=(), computation_time=e.id * 10) for e in executors]
        executors[0].generate_bid.return_value = bids[0]
        executors[1].generate_bid.return_value = bids[1]

        # when
        _, time_taken = allocator.compute_allocation([goal])

        # then
        assert_that(time_taken, equal_to(max(b.computation_time for b in bids)))
