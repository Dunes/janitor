from logging import getLogger
from operator import attrgetter
from decimal import Decimal
from itertools import count, groupby, chain
from weakref import WeakValueDictionary
from abc import abstractmethod, ABCMeta
from copy import deepcopy
from typing import List, Sequence


from action_state import ActionState
from logger import StyleAdapter
from accuracy import as_start_time, INSTANTANEOUS_ACTION_DURATION
from planner import Planner
from planning_exceptions import ExecutionError
from priority_queue import KeyBasedPriorityQueue
from markettaskallocation.common.action import Action, Plan, LocalPlan, Observe, EventAction, Allocate, CombinedAction
from markettaskallocation.common.event import Event
from markettaskallocation.common.goal import Task, Bid, Goal
from markettaskallocation.common.domain_context import DomainContext


__all__ = ["Executor", "AgentExecutor", "EventExecutor", "TaskAllocatorExecutor"]


__author__ = 'jack'
log = StyleAdapter(getLogger(__name__))


class Executor(metaclass=ABCMeta):

    ID_COUNTER = count()
    EXECUTORS = WeakValueDictionary()

    def __init__(self, *, agent, planning_time, deadline):
        self.executing = None
        self._deadline = deadline
        self.agent = agent
        self.planning_time = planning_time
        self.id = next(self.ID_COUNTER)
        self.EXECUTORS[self.id] = self
        self.executed = []

    @property
    def central_executor(self) -> "Executor":
        return self.EXECUTORS[self.central_executor_id]

    @abstractmethod
    def copy(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def deadline(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def has_goals(self):
        raise NotImplementedError

    @abstractmethod
    def next_action(self, time):
        raise NotImplementedError

    @abstractmethod
    def notify_action_starting(self, action_state: ActionState, model):
        raise NotImplementedError

    @abstractmethod
    def notify_action_finishing(self, action_state: ActionState, model):
        self.executed.append(action_state.action)

    @abstractmethod
    def notify_new_knowledge(self, model, time, ids: Sequence[str]):
        raise NotImplementedError

    @classmethod
    def adjust_plan(cls, plan):
        return sorted(cls._adjust_plan_helper(plan), key=attrgetter("start_time", "_ordinal"))

    @staticmethod
    def _adjust_plan_helper(plan):
        for action in plan:
            yield action


class EventExecutor(Executor):
    def __init__(self, *, events, central_executor_id=None):
        super().__init__(agent="event_executor", planning_time=None, deadline=None)
        self.central_executor_id = central_executor_id
        time = attrgetter("time")
        self.events = sorted(events, key=time)
        self.event_actions = []
        for t, events_ in groupby(self.events, key=time):
            self.event_actions.append(EventAction(time=t, events=tuple(events_)))
        self.agent_based_events = []
        self.common_actions = []

    @property
    def known_events(self):
        return [e for e in self.events if not e.hidden] + self.agent_based_events

    def copy(self):
        raise RuntimeError("not implemented for {!r}".format(self))

    def deadline(self):
        return self._deadline

    @property
    def has_goals(self):
        return self.executing or bool(self.event_actions) or bool(self.common_actions)

    def next_action(self, time):
        if self.executing:
            return self.executing
        all_combined_actions = sorted(chain(self.event_actions + self.common_actions), key=attrgetter("start_time"))
        start_time = all_combined_actions[0].start_time
        to_execute_actions = []
        for action_ in all_combined_actions:
            if action_.start_time != start_time:
                break
            to_execute_actions.append(action_)

        assert to_execute_actions

        action = CombinedAction(start_time, to_execute_actions)
        return ActionState(action)

    def notify_action_starting(self, action_state: ActionState, model):
        self.executing = action_state.start()
        changes = action_state.action.apply(model)

        combined_actions = self.executing.action.actions
        for action_ in combined_actions:
            if isinstance(action_, EventAction):
                assert self.event_actions[0] == action_
                del self.event_actions[0]
                for e in action_.events:
                    self.events.remove(e)
            else:
                self.common_actions.remove(action_)

        if changes:
            self.central_executor.notify_new_knowledge(model, action_state.time, changes)

    def notify_action_finishing(self, action_state: ActionState, model):
        super().notify_action_finishing(action_state, model)
        assert self.executing is action_state
        action_state.finish()
        self.executing = None

    def notify_new_knowledge(self, model, time, ids):
        for action_ in self.common_actions:
            for id_ in ids:
                if action_.is_effected_by_change(model, id_):
                    raise RuntimeError("common action {!r} has failed because object {!r} has changed".format(
                        action_, id_
                    ))

    def add_agent_based_events(self, events):
        self.agent_based_events.extend(events)

    def add_common_agent_actions(self, actions):
        assert all(action_.duration == INSTANTANEOUS_ACTION_DURATION for action_ in actions), \
            "common actions need to be instantaneous"
        self.common_actions.extend(actions)
        self.common_actions.sort(key=attrgetter("start_time"))

    def clear_agent_based_actions_and_events(self):
        assert self.executing is None
        self.agent_based_events.clear()
        self.common_actions.clear()


class AgentExecutor(Executor):

    type_ = None
    ignore_internal_events = None

    def __init__(self, *, agent, planning_time, plan=None, deadline=Decimal("Infinity"), central_executor_id=None,
                 halted=False):
        super().__init__(agent=agent, planning_time=planning_time, deadline=deadline)
        self.plan = plan or []
        self.central_executor_id = central_executor_id
        self.halted = halted
        self.won_bids = []

    def copy(self):
        raise TypeError("copying not implemented")
        # log.debug("Executor.copy()")

    @property
    def deadline(self):
        return self._deadline

    @property
    def has_goals(self):
        return bool(self.plan or self.executing)

    def next_action(self, time):
        if self.executing:
            return self.executing
        return ActionState(self.plan[0])

    def notify_action_starting(self, action_state: ActionState, model):
        log.debug("AgentExecutor.notify_action_starting() action_state={}", action_state)
        if self.halted:
            log.debug("{} is halted. Abandoning {}", self.agent, action_state)
            return
        assert not self.executing
        assert self.plan[0] == action_state.action
        del self.plan[0]

        if isinstance(action_state.action, LocalPlan):
            planner = self.central_executor.planner
            action_ = action_state.action
            # NORMAL CASE:
            # An agent has to wait for planning to finish before we can act
            effective_start_time = action_state.time + action_.duration
            if self.bidding_state == "won-extra-dirty-assist":
                # TODO: remove this hack (only works for janitor domain currently) (might passively work for roborescue though)
                # SPECIAL CASE:
                # Some agents have to wait until other agents have planned to be able to plan their-self
                # But all agents have to wait for all agents to finish planning before acting.
                effective_start_time += action_.duration
            planning_model = self.transform_model_for_planning(model, action_.goals)

            new_plan, time_taken = planner.get_plan_and_time_taken(
                planning_model, duration=action_.duration,
                agent=self.agent, goals=action_.goals, metric=action_.metric,
                time=action_state.time,
                events=self.transform_events_for_planning(
                    self.central_executor.event_executor.known_events, planning_model, action_.goals,
                    as_start_time(action_.end_time),
                ),
                effective_start_time=effective_start_time,
            )
            if new_plan is not None:
                plan_action = action_.copy_with(plan=new_plan, duration=time_taken)
                self.executing = ActionState(plan_action, plan_action.start_time).start()
                self.central_executor.notify_goal_realisation(
                    self.extract_events_from_plan(new_plan, action_.goals),
                    self.extract_common_actions_from_plan(new_plan, action_.goals)
                )
            else:
                plan_action = action_.copy_with(failed=True, duration=time_taken)
                self.executing = ActionState(plan_action, plan_action.start_time).start()
                raise ValueError("failed to find any plan for {} trying to achieve {}".format(
                    self.agent, action_.goals))
        else:
            self.executing = action_state.start()
            action_state.action.start(model)

    def notify_action_finishing(self, action_state: ActionState, model):
        if self.halted and action_state != self.executing:
            log.debug("{} is halted. Abandoning {} in favour of partial action", self.agent, action_state)
            return
        super().notify_action_finishing(action_state, model)
        assert self.executing is action_state
        self.executing = None
        action_state = action_state.finish()
        if isinstance(action_state.action, Plan):
            if action_state.action.failed:
                self.central_executor.notify_planning_failure(self.id, action_state.time)
            else:
                self.new_plan(self.adjust_plan(action_state.action.apply(model)))
        else:
            changed = action_state.action.apply(model)
            if changed:
                # new knowledge
                self.central_executor.notify_new_knowledge(model, action_state.time, changed)

    def notify_new_knowledge(self, model, time, ids):
        if not self.plan:
            return
        effected = []
        for action_ in self.plan:
            for id_ in ids:
                if action_.is_effected_by_change(model, id_):
                    effected.append(action_)
                    break
        if effected:
            self.resolve_effected_plan(time, ids, effected)

    @abstractmethod
    def resolve_effected_plan(self, time, changed, effected):
        raise NotImplementedError

    def new_plan(self, plan):
        self.plan = plan
        self.halted = False

    @abstractmethod
    def generate_bid(self, task: Task, planner: Planner, model, time: Decimal, events) -> Bid:
        """
        Generate a bid for a given task.
        :param task: The task to bid for
        :param planner: The planner to use -- mostly just for easy access
        :param model: The current model
        :param time: The current time
        :param events: Any events that may occur in the future
        :return: A bid representing how much the agent values the task and any requirements
        """
        raise NotImplementedError

    @abstractmethod
    def extract_events_from_plan(self, plan: List[Action], goals: List[Goal]) -> List[Event]:
        raise NotImplementedError

    def extract_common_actions_from_plan(self, plan: List[Action], goals: List[Goal]) -> List[Action]:
        raise NotImplementedError

    def halt(self, time):
        """halt all actions at current time
        :param time: Decimal
        """
        log.debug("halting {}", self.agent)
        self.halted = True
        self.plan = []
        self.won_bids = []
        if self.executing and not isinstance(self.executing.action, Observe):
            log.debug("halting {} at {}", self.executing.action, time)
            if self.executing.action.start_time == time:
                # action never started
                self.executing = None
            else:
                new_action = self.executing.action.as_partial(end_time=as_start_time(time))
                if new_action.start_time != self.executing.action.start_time:
                    assert False
                self.executing = ActionState(new_action).start()

    def notify_bid_won(self, bid: Bid, model):
        self.won_bids.append(bid)

    def compute_bid_value(self, task, plan, time):
        """
        :param task: Task
        :param plan: list[Action]
        :param time: Decimal
        :return: Decimal
        """
        makespan = self.get_plan_makespan(plan, time)
        if not self.won_bids:
            return makespan
        return makespan - self.won_bids[-1].estimated_endtime

    @staticmethod
    def get_plan_makespan(plan, time):
        """
        :param plan: list[Action]
        :param time: Decimal
        :return: Decimal
        """
        return as_start_time(plan[-1].end_time) - time

    def transform_model_for_planning(self, model, goals):
        """
        converts a model for planning
        default implementation removes objects that are not the agent represented by this executor or are not nodes
        :param model:
        :param goals:
        :return:
        """
        model = deepcopy(model)
        objects = model["objects"]
        objects[self.type_] = {self.agent: objects[self.type_][self.agent]}
        to_remove = objects.keys() - {"building", "hospital", self.type_}
        for key in to_remove:
            del objects[key]
        return model

    def transform_events_for_planning(self, events, model, goals, execution_start_time):
        """
        removes events not pertinent to the planning problem.
        :param events: list[Event]
        :param goals: list[Goal]
        :param model:
        :return: list[Event]
        """
        new_events = []
        for event in events:
            if event.hidden or (self.ignore_internal_events and not event.external):
                continue
            try:
                event.find_object(model)
            except KeyError:
                continue

            new_events.append(event)
        return new_events


class TaskAllocatorExecutor(Executor):

    valid_goals = True

    def __init__(self, *, agent, planning_time, executor_ids, agent_names, deadline=Decimal("Infinity"), planner,
                 event_executor, domain_context: DomainContext):
        super().__init__(agent=agent, planning_time=planning_time, deadline=deadline)
        self.valid_plan = False
        self.planner = planner
        self.event_executor = event_executor if event_executor else EventExecutor(events=())
        self.executor_ids = executor_ids
        assert len(executor_ids) == len(agent_names)
        self.agent_executor_map = {name: id_ for name, id_ in zip(agent_names, executor_ids)}
        self.domain_context = domain_context

    def copy(self):
        raise NotImplementedError

    @property
    def _executors(self):
        """

        :return: "list[AgentExecutor]"
        """
        for executor_id in self.executor_ids:
            yield self.EXECUTORS[executor_id]

    def executor_by_name(self, name):
        return self.EXECUTORS[self.agent_executor_map[name]]

    @property
    def deadline(self):
        return self._deadline

    @deadline.setter
    def deadline(self, deadline):
        if self.executing:
            raise ExecutionError("Wasn't expecting to be told deadline is changing when already planning")
        self._deadline = deadline

    @property
    def has_goals(self):
        # has a goal if no valid plan and still unobtained goals that are possible
        if not self.valid_goals:
            return False
        if not self.valid_plan:
            return True
        if not any(e.has_goals for e in self._executors):
            self.valid_plan = False
            return True
        return False

    def next_action(self, time):
        assert not self.valid_plan
        if self.executing:
            return self.executing
        return ActionState(Allocate(as_start_time(time), agent=self.agent))

    def notify_action_starting(self, action_state: ActionState, model):
        assert not self.executing
        if not isinstance(action_state.action, Allocate):
            raise ExecutionError("Have a non-allocate action: " + str(action_state.action))

        for e in self._executors:
            e.halt(action_state.time)
        self.event_executor.clear_agent_based_actions_and_events()

        tasks = self.domain_context.compute_tasks(model, action_state.time)
        if not tasks:
            log.info("All goals are in the past or achieved -- halting")
            # nothing more to do
            self.valid_goals = False
            self.executing = None
            return

        allocation, computation_time = self.compute_allocation(tasks, model, action_state.time)

        if not allocation:
            log.info("No goal can be achieved -- halting")
            # nothing more that can be done
            self.valid_goals = False
            self.executing = None
            return

        action_ = action_state.action.copy_with(allocation=allocation, duration=computation_time)
        self.executing = ActionState(action_).start()

    def notify_action_finishing(self, action_state: ActionState, model):
        super().notify_action_finishing(action_state, model)
        assert self.executing is action_state
        self.executing = None
        action_state = action_state.finish()

        plan_start = as_start_time(action_state.time)
        delayed_start = plan_start + self.planning_time

        bids = sorted(action_state.action.allocation, key=attrgetter("agent"))
        for agent, agent_bids in groupby(bids, key=attrgetter("agent")):
            agent_bids = list(agent_bids)
            executor = self.executor_by_name(agent)
            if any(bid.requirements for bid in executor.won_bids):
                start_time = delayed_start
            else:
                start_time = plan_start

            goals = [b.task.goal for b in agent_bids]
            metric = self.domain_context.get_metric_from_tasks([b.task for b in agent_bids], model["metric"])
            executor.new_plan([LocalPlan(
                start_time=start_time,
                duration=self.planning_time,
                agent=agent,
                goals=goals,
                metric=metric
            )])

        self.valid_plan = True

    def notify_new_knowledge(self, model, time, ids):
        for executor_id in self.executor_ids:
            self.EXECUTORS[executor_id].notify_new_knowledge(model, time, ids)

    def notify_planning_failure(self, executor_id, time):
        self.valid_plan = False
        # tell all agents to stop immediately
        for e_id in self.executor_ids:
            self.EXECUTORS[e_id].halt(time)

    def compute_allocation(self, tasks, model, time):
        tasks = KeyBasedPriorityQueue(tasks, key=self.domain_context.task_key_for_allocation)
        allocation = {}
        computation_time = 0

        while tasks:
            task = Task.combine(tasks.pop_equal())

            if task.goal in allocation:
                # there is already already an agent assigned to this goal (and deadline)
                current_bid = allocation[task.goal]
                new_bid = current_bid._replace(task=Task.combine([current_bid.task, task]))
                allocation[task.goal] = new_bid
                continue

            bids = [e.generate_bid(task, self.planner, model, time, self.event_executor.known_events)
                    for e in self._executors]
            bids = [b for b in bids if b is not None]  # filter out failed bids

            if not bids:
                log.debug("no bids for {}", task)
                continue

            # parallel computation -- only take longest
            computation_time += max(b.computation_time for b in bids)
            winning_bid = min(bids, key=attrgetter("estimated_endtime"))

            # notify winner of winning bid
            allocation[winning_bid.task.goal] = winning_bid
            self.executor_by_name(winning_bid.agent).notify_bid_won(winning_bid, model)

            # add additional goals if not already met
            tasks.extend(winning_bid.requirements)

        result = sorted(allocation.values(), key=attrgetter("task.goal.deadline")), computation_time
        log.info("allocation: {}", result[0])
        return result

    def notify_goal_realisation(self, events, actions):
        """
        :param events: list[Event]
        :param actions list[Action]
        :return:
        """
        self.event_executor.add_agent_based_events(events)
        self.event_executor.add_common_agent_actions(actions)
