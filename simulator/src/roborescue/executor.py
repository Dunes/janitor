from logging import getLogger
from operator import attrgetter
from decimal import Decimal
from itertools import count, groupby
from weakref import WeakValueDictionary
from abc import abstractmethod, ABCMeta
from copy import deepcopy

from .action import Action, Plan, LocalPlan, Observe, Move, Unblock, Unload, Rescue, EventAction, Allocate
from action_state import ActionState, ExecutionState
from logger import StyleAdapter
from planning_exceptions import ExecutionError, NoPlanException
from accuracy import as_start_time, as_next_end_time, zero
from priority_queue import PriorityQueue
from roborescue.goal import Goal, Task, Bid
from roborescue.event import Event, EdgeEvent, ObjectEvent, Predicate
from planner import Planner
from .problem_encoder import find_object


__author__ = 'jack'
log = StyleAdapter(getLogger(__name__))


CIVILIAN_VALUE = Decimal(1000)


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
    def central_executor(self):
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
    def notify_new_knowledge(self, time, node):
        raise NotImplementedError

    @classmethod
    def adjust_plan(cls, plan):
        return sorted(cls._adjust_plan_helper(plan), key=attrgetter("start_time", "_ordinal"))

    @staticmethod
    def _adjust_plan_helper(plan):
        for action in plan:
            yield action
            if type(action) is Move:
                yield Observe(action.end_time, action.agent, action.end_node)


class EventExecutor(Executor):
    def __init__(self, *, events, central_executor_id=None):
        super().__init__(agent="event_executor", planning_time=None, deadline=None)
        self.central_executor_id = central_executor_id
        time = attrgetter("time")
        self.events = sorted(events, key=time)
        self.event_actions = []
        for t, evts in groupby(self.events, key=time):
            self.event_actions.append(EventAction(time=t, events=tuple(evts)))
        self.agent_based_events = []

    @property
    def known_events(self):
        return [e for e in self.events if not e.hidden] + self.agent_based_events

    def copy(self):
        raise NotImplementedError

    def deadline(self):
        return self._deadline

    @property
    def has_goals(self):
        return self.executing or bool(self.event_actions)

    def next_action(self, time):
        if self.executing:
            return self.executing
        action = self.event_actions[0]
        return ActionState(action)

    def notify_action_starting(self, action_state: ActionState, model):
        self.executing = action_state.start()
        del self.event_actions[0]
        changes = action_state.action.apply(model)
        for e in action_state.action.events:
            self.events.remove(e)
        self.central_executor.notify_new_knowledge(action_state.time, changes)

    def notify_action_finishing(self, action_state: ActionState, model):
        super().notify_action_finishing(action_state, model)
        assert self.executing is action_state
        action_state.finish()
        self.executing = None

    def notify_new_knowledge(self, time, node):
        pass


class AgentExecutor(Executor):

    def __init__(self, *, agent, planning_time, plan=None, deadline=Decimal("Infinity"), central_executor_id=None,
                 halted=False):
        super().__init__(agent=agent, planning_time=planning_time, deadline=deadline)
        self.plan = plan or []
        self.central_executor_id = central_executor_id
        self.halted = halted
        self.goals = []

    def copy(self):
        raise TypeError("copying not implemented")
        log.debug("Executor.copy()")

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
            planner = self.central_executor.local_planner
            action_ = action_state.action
            try:
                # subtract planning time to create "instantaneous" plan
                new_plan, time_taken = planner.get_plan_and_time_taken(
                    model, duration=planner.planning_time, agent=self.agent, goals=action_.goals,
                    metric=None, time=action_state.time - planner.planning_time,
                    events=action_.local_events + self.central_executor.event_executor.known_events)
                plan_action = action_.copy_with(plan=new_plan, duration=zero)
                self.executing = ActionState(plan_action, plan_action.start_time).start()
                self.central_executor.notify_goal_realisation(self.extract_events(new_plan, action_.goals))
            except NoPlanException:
                self.central_executor.notify_planning_failure(self.id, action_state.time)
        else:
            self.executing = action_state.start()

    def notify_action_finishing(self, action_state: ActionState, model):
        if self.halted and action_state != self.executing:
            log.debug("{} is halted. Abandoning {} in favour of partial action", self.agent, action_state)
            return
        super().notify_action_finishing(action_state, model)
        assert self.executing is action_state
        self.executing = None
        action_state = action_state.finish()
        if isinstance(action_state.action, Plan):
            self.new_plan(self.adjust_plan(action_state.action.apply(model)))
        else:
            changes = action_state.action.apply(model)
            if changes:
                # new knowledge
                self.central_executor.notify_new_knowledge(action_state.time, changes)

    def notify_new_knowledge(self, time, changes):
        if not self.plan:
            return
        for change in changes:
            for action_ in self.plan:
                if action_.is_effected_by_change(change):
                    goals = self.extract_goals(self.plan)
                    events = self.extract_events(self.plan, as_start_time(time))
                    if not goals:
                        log.warning("{} has actions, but none are goal orientated -- not bothering to replan for "
                                    "these goals", self.agent)
                        self.plan = []
                        return
                    else:
                        self.halt(time)
                        self.new_plan([LocalPlan(as_start_time(time), self.planning_time, self.agent, goals=goals,
                                           local_events=events)])
                        return

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

    @staticmethod
    @abstractmethod
    def extract_events(plan: "list[Action]", goals: "list[Goal]") -> "list[Event]":
        """
        :param plan: list[Action]
        :param goals: list[Goal]
        :return: list[Event]
        """
        raise NotImplementedError

    def halt(self, time):
        """halt all actions at current time"""
        log.debug("halting {}", self.agent)
        self.halted = True
        self.plan = []
        self.goals = []
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

    def notify_bid_won(self, bid: Bid):
        self.goals.append(bid)

    def compute_bid_value(self, task: Task, plan: "list[Action]", time: Decimal) -> Decimal:
        plan_length_discount = 1 - (1 / (self.get_plan_makespan(plan, time) + 1))
        other_goals_cost = sum(bid.value for bid in self.goals)
        return task.value * plan_length_discount + other_goals_cost

    @staticmethod
    def get_plan_makespan(plan: "list[Action]", time: Decimal) -> Decimal:
        if not plan:
            return Decimal(0)
        return as_start_time(plan[-1].end_time) - time


class PoliceExecutor(AgentExecutor):

    def extract_events(self, plan, goals):
        events = []
        unblocks = [(a, {a.start_node, a.end_node}) for a in plan if isinstance(a, Unblock)]
        edges = set(frozenset(g.predicate[1:]) for g in goals)
        for edge in edges:
            start, end = edge
            for u, unblock_nodes in unblocks:
                if edge == unblock_nodes:
                    events.append(self.create_clear_edge_event(as_start_time(u.end_time), start, end))
                    events.append(self.create_clear_edge_event(as_start_time(u.end_time), end, start))
                    break
            else:
                raise ValueError("no matching unblock for unblock goal: {}".format(edge))

        return events

    @staticmethod
    def create_clear_edge_event(time, start_node, end_node):
        return EdgeEvent(
            time=time,
            id_="{} {}".format(start_node, end_node),
            predicates=[
                Predicate(name="edge", becomes=True),
                Predicate(name="blocked-edge", becomes=False),
            ],
            hidden=False
        )

    def generate_bid(self, task: Task, planner: Planner, model, time, events) -> Bid:
        try:
            plan, time_taken = planner.get_plan_and_time_taken(
                model=model,
                duration=self.planning_time,
                agent=self.agent,
                goals=[task.goal],
                metric=None,
                time=time,
                events=events
            )
        except NoPlanException:
            return None

        return Bid(agent=self.agent,
                   value=self.compute_bid_value(task, plan, time),
                   task=task,
                   requirements=(),
                   computation_time=time_taken)


class MedicExecutor(AgentExecutor):

    def extract_events(self, plan, goals):
        events = []
        rescues = [a for a in plan if isinstance(a, Rescue)]
        for goal in goals:
            target = goal.predicate[1]
            for r in rescues:
                if target == r.target:
                    events.append(self.create_rescue_civilian_event(as_start_time(r.end_time), target))
                    break
            else:
                raise ValueError("no matching Rescue for goal: {}".format(goal))

        return events

    @staticmethod
    def create_rescue_civilian_event(time, civ_id):
        return ObjectEvent(
            time=time,
            id_=civ_id,
            predicates=[
                Predicate(name="rescued", becomes=True),
            ],
            hidden=False
        )

    @staticmethod
    def remove_blocks_from_model(model):
        """
        creates a copy of the model with all road blocks removed
        :param model:
        :return:
        """
        model = dict(model, graph=deepcopy(model["graph"]))
        for edge in model["graph"]["edges"].values():
            edge["known"] = {
                "edge": True,
                "blocked-edge": False,
                "distance": edge["known"]["distance"]
            }
        return model

    def generate_bid(self, task: Task, planner: Planner, model, time, events) -> Bid:
        try:
            plan, time_taken = planner.get_plan_and_time_taken(
                model=self.remove_blocks_from_model(model),
                duration=self.planning_time,
                agent=self.agent,
                goals=[task.goal],
                metric=None,
                time=time - self.planning_time,  # instantaneous plan?
                events=events
            )
        except NoPlanException:
            return None

        model_edges = model["graph"]["edges"]
        blocked_edge_actions = [a for a in plan if isinstance(a, Move) and not model_edges[a.edge]["known"]["edge"]]
        bid_value = self.compute_bid_value(task, plan, time)
        task_value = (bid_value / len(blocked_edge_actions)) if blocked_edge_actions else 0
        spare_time = task.goal.deadline - as_start_time(plan[-1].end_time)
        requirements = tuple(
            Task(goal=Goal(predicate=("edge", a.start_node, a.end_node), deadline=a.start_time + spare_time), value=task_value)
            for a in blocked_edge_actions
        )

        return Bid(agent=self.agent,
                   value=bid_value,
                   task=task,
                   requirements=requirements,
                   computation_time=time_taken)


class CentralPlannerExecutor(Executor):

    planning_possible = True

    def __init__(self, *, agent, planning_time, executor_ids, agent_names, deadline=Decimal("Infinity"),
                 central_planner, local_planner, event_executor):
        super().__init__(agent=agent, planning_time=planning_time, deadline=deadline)
        self.valid_plan = False
        self.central_planner = central_planner
        self.local_planner = local_planner
        self.event_executor = event_executor if event_executor else EventExecutor(events=())
        self.executor_ids = executor_ids
        assert len(executor_ids) == len(agent_names)
        self.agent_executor_map = {name: id_ for name, id_ in zip(agent_names, executor_ids)}

    def copy(self):
        raise NotImplementedError

    @property
    def _executors(self):
        for executor_id in self.executor_ids:
            yield self.EXECUTORS[executor_id]

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
        if not self.valid_plan:
            return True
        if not self.planning_possible:
            return False
        if not any(e.has_goals for e in self._executors):
            self.valid_plan = False
            return True
        return False

    def next_action(self, time):
        assert not self.valid_plan
        if self.executing:
            return self.executing
        return ActionState(Plan(as_start_time(time), self.planning_time))

    def notify_action_starting(self, action_state: ActionState, model):
        assert not self.executing

        if not isinstance(action_state.action, Plan):
            raise ExecutionError("Have a non-plan action: " + str(action_state.action))

        try:
            new_plan, time_taken = self.central_planner.get_plan_and_time_taken(
                model, duration=self.central_planner.planning_time, agent="all", goals=model["goal"],
                metric=model["metric"], time=action_state.time, events=self.event_executor.known_events
            )
        except NoPlanException:
            new_plan, time_taken = [], self.central_planner.planning_time
            self.planning_possible = False

        new_plan = self.adjust_plan(new_plan)
        plan_action = action_state.action.copy_with(plan=new_plan, duration=time_taken)
        self.executing = ActionState(plan_action).start()

    def notify_action_finishing(self, action_state: ActionState, model):
        super().notify_action_finishing(action_state, model)
        assert self.executing is action_state
        self.executing = None
        action_state = action_state.finish()
        plan = action_state.action.apply(model)

        # disseminate plan
        for agent, sub_plan in self.disseminate_plan(plan):
            sub_plan = list(sub_plan)
            self.EXECUTORS[self.agent_executor_map[agent]].new_plan(list(sub_plan))

        self.valid_plan = True

    def notify_new_knowledge(self, time, node):
        for e in self._executors:
            e.notify_new_knowledge(time, node)

    def notify_planning_failure(self, executor_id, time):
        self.valid_plan = False
        # tell all agents to stop immediately
        for e in self._executors:
            e.halt(time)

    @staticmethod
    def disseminate_plan(plan):
        plan = sorted(plan, key=attrgetter("agent", "start_time"))
        return groupby(plan, key=attrgetter("agent"))


class TaskAllocatorExecutor(Executor):

    valid_goals = True

    def __init__(self, *, agent, planning_time, executor_ids, agent_names, deadline=Decimal("Infinity"),
                 central_planner, local_planner, event_executor):
        super().__init__(agent=agent, planning_time=planning_time, deadline=deadline)
        self.valid_plan = False
        self.central_planner = central_planner
        self.local_planner = local_planner
        self.event_executor = event_executor if event_executor else EventExecutor(events=())
        self.executor_ids = executor_ids
        assert len(executor_ids) == len(agent_names)
        self.agent_executor_map = {name: id_ for name, id_ in zip(agent_names, executor_ids)}

    def copy(self):
        raise NotImplementedError

    @property
    def _executors(self) -> "list[AgentExecutor]":
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
        self.event_executor.agent_based_events.clear()

        tasks = self.compute_tasks(model["goal"]["soft-goals"], model["events"], model["objects"], action_state.time)
        if not tasks:
            # nothing more to do
            self.valid_goals = False
            self.executing = None
            return

        allocation, computation_time = self.compute_allocation(tasks, model, action_state.time)
        action_ = action_state.action.copy_with(allocation=allocation, duration=computation_time)
        self.executing = ActionState(action_).start()

    def notify_action_finishing(self, action_state: ActionState, model):
        super().notify_action_finishing(action_state, model)
        assert self.executing is action_state
        self.executing = None
        action_state = action_state.finish()

        plan_start = as_start_time(action_state.time)

        bids = sorted(action_state.action.allocation, key=attrgetter("agent"))
        for agent, agent_bids in groupby(bids, key=attrgetter("agent")):
            self.executor_by_name(agent).new_plan([LocalPlan(
                start_time=plan_start,
                duration=self.planning_time,
                agent=agent,
                goals=[b.task.goal for b in agent_bids],
                local_events=[]
            )])

        self.valid_plan = True

    def notify_new_knowledge(self, time, node):
        for executor_id in self.executor_ids:
            self.EXECUTORS[executor_id].notify_new_knowledge(time, node)

    def notify_planning_failure(self, executor_id, time):
        self.valid_plan = False
        # tell all agents to stop immediately
        for e_id in self.executor_ids:
            self.EXECUTORS[e_id].halt(time)

    @staticmethod
    def compute_tasks(goals, events: "list[Event]", objects, time):
        """
        Takes a set of goals and events from a model and computes a list of Tasks for it
        :param goals:
        :param events: list[Event]
        :param objects:
        :param time:
        :return: list[Task]
        """
        tasks = []
        for g in goals:
            civ_id = g[1]
            civ = find_object(civ_id, objects)
            if civ["known"].get("rescued"):
                # goal already achieved
                continue
            for e in events:
                if e.id_ == civ_id and any((p.name == "alive" and p.becomes is False) for p in e.predicates):
                    deadline = e.time
                    break
            else:
                deadline = Decimal("inf")
            if deadline <= time:
                # deadline already elapsed -- cannot achieve this goal
                continue
            t = Task(Goal(tuple(g), deadline), CIVILIAN_VALUE)
            tasks.append(t)
        return tasks

    def compute_allocation(self, tasks, model, time):
        tasks = PriorityQueue(tasks, key=attrgetter("goal.deadline", "goal.predicate"))
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

            bids = [e.generate_bid(task, self.local_planner, model, time, self.event_executor.known_events)
                    for e in self._executors]
            bids = [b for b in bids if b is not None]  # filter out failed bids

            # parallel computation -- only take longest
            computation_time += max(b.computation_time for b in bids)
            winning_bid = min(bids, key=attrgetter("value"))

            # notify winner of winning bid
            allocation[winning_bid.task.goal] = winning_bid
            self.executor_by_name(winning_bid.agent).notify_bid_won(winning_bid)

            # add additional goals if not already met
            tasks.extend(winning_bid.requirements)

        return sorted(allocation.values(), key=attrgetter("task.goal.deadline")), computation_time

    def notify_goal_realisation(self, events: "list[Event]"):
        self.event_executor.agent_based_events.extend(events)
