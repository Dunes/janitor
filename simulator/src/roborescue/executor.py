from logging import getLogger
from operator import attrgetter
from decimal import Decimal
from itertools import count, groupby
from weakref import WeakValueDictionary
from abc import abstractmethod, ABCMeta
from copy import deepcopy

from .action import Action, Plan, LocalPlan, Observe, Move, Unblock, Rescue, EventAction, Allocate \
    , Load, Unload
from action_state import ActionState
from logger import StyleAdapter
from planning_exceptions import ExecutionError
from accuracy import as_start_time
from priority_queue import PriorityQueue
from roborescue.goal import Goal, Task, Bid
from roborescue.event import Event, EdgeEvent, ObjectEvent, Predicate
from planner import Planner
from .problem_encoder import find_object


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

    @staticmethod
    def get_metric_from_tasks(tasks, base_metric):
        """
        :param tasks: list[Task]
        :param base_metric: dict
        :return: dict[Goal, Decimal]
        """
        metric = deepcopy(base_metric)
        violations = metric["weights"]["soft-goal-violations"]
        violations.update((task.goal, task.value) for task in tasks)
        return metric


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
            # remove from here
            if action_state.action.agent == "medic1":
                time_taken = Decimal("0.1")
                new_plan = [Move(start_time=Decimal('15'), duration=Decimal('120'), agent='medic1', start_node='hospital0-0', end_node='building0-1'), Rescue(start_time=Decimal('135'), duration=Decimal('60'), agent='medic1', target='civ1', node='building0-1'), Load(start_time=Decimal('195'), duration=Decimal('30'), agent='medic1', target='civ1', node='building0-1'), Move(start_time=Decimal('225'), duration=Decimal('120'), agent='medic1', start_node='building0-1', end_node='hospital0-0'), Unload(start_time=Decimal('345'), duration=Decimal('30'), agent='medic1', target='civ1', node='hospital0-0'), Move(start_time=Decimal('375'), duration=Decimal('120'), agent='medic1', start_node='hospital0-0', end_node='building0-1'), Move(start_time=Decimal('495'), duration=Decimal('120'), agent='medic1', start_node='building0-1', end_node='building1-1'), Rescue(start_time=Decimal('615'), duration=Decimal('60'), agent='medic1', target='civ8', node='building1-1'), Load(start_time=Decimal('675'), duration=Decimal('30'), agent='medic1', target='civ8', node='building1-1'), Move(start_time=Decimal('705'), duration=Decimal('120'), agent='medic1', start_node='building1-1', end_node='building2-1'), Rescue(start_time=Decimal('825'), duration=Decimal('60'), agent='medic1', target='civ2', node='building2-1'), Rescue(start_time=Decimal('885'), duration=Decimal('60'), agent='medic1', target='civ10', node='building2-1'), Move(start_time=Decimal('945'), duration=Decimal('120'), agent='medic1', start_node='building2-1', end_node='building1-1'), Move(start_time=Decimal('1065'), duration=Decimal('120'), agent='medic1', start_node='building1-1', end_node='building0-1'), Move(start_time=Decimal('1185'), duration=Decimal('120'), agent='medic1', start_node='building0-1', end_node='hospital0-0'), Unload(start_time=Decimal('1305'), duration=Decimal('30'), agent='medic1', target='civ8', node='hospital0-0'), Move(start_time=Decimal('1335'), duration=Decimal('120'), agent='medic1', start_node='hospital0-0', end_node='building0-1'), Move(start_time=Decimal('1455'), duration=Decimal('120'), agent='medic1', start_node='building0-1', end_node='building0-2'), Rescue(start_time=Decimal('1575'), duration=Decimal('60'), agent='medic1', target='civ0', node='building0-2'), Load(start_time=Decimal('1635'), duration=Decimal('30'), agent='medic1', target='civ0', node='building0-2'), Move(start_time=Decimal('1665'), duration=Decimal('120'), agent='medic1', start_node='building0-2', end_node='building0-3'), Rescue(start_time=Decimal('1785'), duration=Decimal('60'), agent='medic1', target='civ5', node='building0-3'), Move(start_time=Decimal('1845'), duration=Decimal('120'), agent='medic1', start_node='building0-3', end_node='building0-2'), Move(start_time=Decimal('1965'), duration=Decimal('120'), agent='medic1', start_node='building0-2', end_node='building0-1'), Move(start_time=Decimal('2085'), duration=Decimal('120'), agent='medic1', start_node='building0-1', end_node='hospital0-0'), Unload(start_time=Decimal('2205'), duration=Decimal('30'), agent='medic1', target='civ0', node='hospital0-0'), Move(start_time=Decimal('2235'), duration=Decimal('120'), agent='medic1', start_node='hospital0-0', end_node='building0-1'), Move(start_time=Decimal('2355'), duration=Decimal('120'), agent='medic1', start_node='building0-1', end_node='building1-1'), Move(start_time=Decimal('2475'), duration=Decimal('120'), agent='medic1', start_node='building1-1', end_node='building2-1'), Load(start_time=Decimal('2595'), duration=Decimal('30'), agent='medic1', target='civ2', node='building2-1'), Move(start_time=Decimal('2625'), duration=Decimal('120'), agent='medic1', start_node='building2-1', end_node='building1-1'), Move(start_time=Decimal('2745'), duration=Decimal('120'), agent='medic1', start_node='building1-1', end_node='building0-1'), Move(start_time=Decimal('2865'), duration=Decimal('120'), agent='medic1', start_node='building0-1', end_node='hospital0-0'), Unload(start_time=Decimal('2985'), duration=Decimal('30'), agent='medic1', target='civ2', node='hospital0-0'), Move(start_time=Decimal('3015'), duration=Decimal('120'), agent='medic1', start_node='hospital0-0', end_node='building0-1'), Move(start_time=Decimal('3135'), duration=Decimal('120'), agent='medic1', start_node='building0-1', end_node='building1-1'), Move(start_time=Decimal('3255'), duration=Decimal('120'), agent='medic1', start_node='building1-1', end_node='building2-1'), Load(start_time=Decimal('3375'), duration=Decimal('30'), agent='medic1', target='civ10', node='building2-1'), Move(start_time=Decimal('3405'), duration=Decimal('120'), agent='medic1', start_node='building2-1', end_node='building1-1'), Move(start_time=Decimal('3525'), duration=Decimal('120'), agent='medic1', start_node='building1-1', end_node='building0-1'), Move(start_time=Decimal('3645'), duration=Decimal('120'), agent='medic1', start_node='building0-1', end_node='hospital0-0'), Unload(start_time=Decimal('3765'), duration=Decimal('30'), agent='medic1', target='civ10', node='hospital0-0'), Move(start_time=Decimal('3795'), duration=Decimal('120'), agent='medic1', start_node='hospital0-0', end_node='building0-1'), Move(start_time=Decimal('3915'), duration=Decimal('120'), agent='medic1', start_node='building0-1', end_node='building0-2'), Move(start_time=Decimal('4035'), duration=Decimal('120'), agent='medic1', start_node='building0-2', end_node='building0-3'), Load(start_time=Decimal('4155'), duration=Decimal('30'), agent='medic1', target='civ5', node='building0-3'), Move(start_time=Decimal('4185'), duration=Decimal('120'), agent='medic1', start_node='building0-3', end_node='building0-4'), Rescue(start_time=Decimal('4305'), duration=Decimal('60'), agent='medic1', target='civ7', node='building0-4'), Rescue(start_time=Decimal('4365'), duration=Decimal('60'), agent='medic1', target='civ4', node='building0-4'), Move(start_time=Decimal('4425'), duration=Decimal('120'), agent='medic1', start_node='building0-4', end_node='building1-4'), Move(start_time=Decimal('4545'), duration=Decimal('120'), agent='medic1', start_node='building1-4', end_node='building2-4'), Move(start_time=Decimal('4665'), duration=Decimal('120'), agent='medic1', start_node='building2-4', end_node='hospital3-4'), Unload(start_time=Decimal('4785'), duration=Decimal('30'), agent='medic1', target='civ5', node='hospital3-4'), Move(start_time=Decimal('4815'), duration=Decimal('120'), agent='medic1', start_node='hospital3-4', end_node='building2-4'), Move(start_time=Decimal('4935'), duration=Decimal('120'), agent='medic1', start_node='building2-4', end_node='building1-4'), Move(start_time=Decimal('5055'), duration=Decimal('120'), agent='medic1', start_node='building1-4', end_node='building0-4'), Load(start_time=Decimal('5175'), duration=Decimal('30'), agent='medic1', target='civ7', node='building0-4'), Move(start_time=Decimal('5205'), duration=Decimal('120'), agent='medic1', start_node='building0-4', end_node='building1-4'), Move(start_time=Decimal('5325'), duration=Decimal('120'), agent='medic1', start_node='building1-4', end_node='building2-4'), Move(start_time=Decimal('5445'), duration=Decimal('120'), agent='medic1', start_node='building2-4', end_node='hospital3-4'), Unload(start_time=Decimal('5565'), duration=Decimal('30'), agent='medic1', target='civ7', node='hospital3-4'), Move(start_time=Decimal('5595'), duration=Decimal('120'), agent='medic1', start_node='hospital3-4', end_node='building2-4'), Move(start_time=Decimal('5715'), duration=Decimal('120'), agent='medic1', start_node='building2-4', end_node='building1-4'), Move(start_time=Decimal('5835'), duration=Decimal('120'), agent='medic1', start_node='building1-4', end_node='building0-4'), Load(start_time=Decimal('5955'), duration=Decimal('30'), agent='medic1', target='civ4', node='building0-4'), Move(start_time=Decimal('5985'), duration=Decimal('120'), agent='medic1', start_node='building0-4', end_node='building1-4'), Move(start_time=Decimal('6105'), duration=Decimal('120'), agent='medic1', start_node='building1-4', end_node='building2-4'), Move(start_time=Decimal('6225'), duration=Decimal('120'), agent='medic1', start_node='building2-4', end_node='hospital3-4'), Unload(start_time=Decimal('6345'), duration=Decimal('30'), agent='medic1', target='civ4', node='hospital3-4')]
            else:
                new_plan, time_taken = planner.get_plan_and_time_taken(
                    model, duration=action_.duration, agent=self.agent, goals=action_.goals,
                    metric=action_.metric, time=action_state.time,
                    events=self.central_executor.event_executor.known_events)
            # to here
            if new_plan is not None:
                plan_action = action_.copy_with(plan=new_plan, duration=time_taken)
                self.executing = ActionState(plan_action, plan_action.start_time).start()
                self.central_executor.notify_goal_realisation(self.extract_events(new_plan, action_.goals))
            else:
                plan_action = action_.copy_with(failed=True, duration=time_taken)
                self.executing = ActionState(plan_action, plan_action.start_time).start()
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
            if action_state.action.failed:
                self.central_executor.notify_planning_failure(self.id, action_state.time)
            else:
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
                    raise NotImplementedError("need to create metric from tasks")
                    # goals = [bid.task.goal for bid in self.won_bids]
                    # self.halt(time)
                    # # No metric. Can either still complete all goals or not
                    # self.new_plan([LocalPlan(as_start_time(time), self.central_executor.planning_time,
                    #                          self.agent, goals=goals, metric=None)])
                    # return

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
    def extract_events(self, plan, goals):
        """
        :param plan: list[Action]
        :param goals: list[Goal]
        :return: list[Event]
        """
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

    def notify_bid_won(self, bid: Bid):
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


class PoliceExecutor(AgentExecutor):

    def extract_events(self, plan, goals):
        """

        :param plan: list[Action]
        :param goals: list[Goal]
        :return: list[Event]
        """
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
        if "rescued" in task.goal.predicate:
            return None
        plan, time_taken = planner.get_plan_and_time_taken(
            model=model,
            duration=self.planning_time,
            agent=self.agent,
            goals=[task.goal] + [b.task.goal for b in self.won_bids],
            metric=None,
            time=time,
            events=events
        )
        if plan is None:
            return None

        return Bid(agent=self.agent,
                   estimated_endtime=as_start_time(plan[-1].end_time),
                   additional_cost=self.compute_bid_value(task, plan, time),
                   task=task,
                   requirements=(),
                   computation_time=time_taken)


class MedicExecutor(AgentExecutor):

    def extract_events(self, plan, goals):
        """

        :param plan: list[Action]
        :param goals: list[Goal]
        :return: list[Event]
        """
        events = []
        rescues = [a for a in plan if isinstance(a, Rescue)]
        for goal in goals:
            target = goal.predicate[1]
            for r in rescues:
                if target == r.target:
                    events.append(self.create_rescue_civilian_event(as_start_time(r.end_time), target))
                    break
            else:
                log.info("{} not found in plan.".format(goal))
                # raise ValueError("no matching Rescue for goal: {}".format(goal))

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
        if "edge" in task.goal.predicate:
            return None
        plan, time_taken = planner.get_plan_and_time_taken(
            model=self.remove_blocks_from_model(model),
            duration=self.planning_time,
            agent=self.agent,
            goals=[task.goal] + [b.task.goal for b in self.won_bids],
            metric=None,
            time=time - self.planning_time,  # instantaneous plan?
            events=events
        )
        if plan is None:
            return None

        model_edges = model["graph"]["edges"]
        blocked_edge_actions = [a for a in plan if isinstance(a, Move) and not model_edges[a.edge]["known"]["edge"]]
        bid_value = self.compute_bid_value(task, plan, time)
        if blocked_edge_actions:
            task_value = task.value / len(blocked_edge_actions)
            spare_time = task.goal.deadline - as_start_time(plan[-1].end_time)
            requirements = tuple(
                Task(goal=Goal(predicate=("edge", a.start_node, a.end_node), deadline=a.start_time + spare_time), value=task_value)
                for a in blocked_edge_actions
            )
        else:
            requirements = ()

        return Bid(agent=self.agent,
                   estimated_endtime=as_start_time(plan[-1].end_time),
                   additional_cost=bid_value,
                   task=task,
                   requirements=requirements,
                   computation_time=time_taken)


class TaskAllocatorExecutor(Executor):

    valid_goals = True

    def __init__(self, *, agent, planning_time, executor_ids, agent_names, deadline=Decimal("Infinity"), planner,
                 event_executor):
        super().__init__(agent=agent, planning_time=planning_time, deadline=deadline)
        self.valid_plan = False
        self.planner = planner
        self.event_executor = event_executor if event_executor else EventExecutor(events=())
        self.executor_ids = executor_ids
        assert len(executor_ids) == len(agent_names)
        self.agent_executor_map = {name: id_ for name, id_ in zip(agent_names, executor_ids)}

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
        self.event_executor.agent_based_events.clear()

        tasks = self.compute_tasks(model["goal"]["soft-goals"],
                                   model["metric"]["weights"]["soft-goal-violations"]["rescued"],
                                   model["events"], model["objects"], action_state.time)
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
            metric = self.get_metric_from_tasks([b.task for b in agent_bids], model["metric"])
            executor.new_plan([LocalPlan(
                start_time=start_time,
                duration=self.planning_time,
                agent=agent,
                goals=goals,
                metric=metric
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
    def compute_tasks(goals, value, events, objects, time):
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
                log.info("deadline for rescuing {!r} already elapsed".format(civ_id))
                continue
            t = Task(Goal(tuple(g), deadline), value)
            tasks.append(t)
        return tasks

    def compute_allocation(self, tasks, model, time):
        tasks = PriorityQueue(tasks, key=attrgetter("goal.deadline", "goal.predicate"))
        allocation = {}
        computation_time = 0

        # remove from here
        allocation = {Goal(predicate=('rescued', 'civ7'), deadline=Decimal('Infinity')): Bid(agent='medic1', estimated_endtime=Decimal('5520'), additional_cost=Decimal('840'), task=Task(goal=Goal(predicate=('rescued', 'civ7'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('1')), Goal(predicate=('rescued', 'civ8'), deadline=Decimal('Infinity')): Bid(agent='medic1', estimated_endtime=Decimal('6360'), additional_cost=Decimal('840'), task=Task(goal=Goal(predicate=('rescued', 'civ8'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('1')), Goal(predicate=('rescued', 'civ5'), deadline=Decimal('Infinity')): Bid(agent='medic1', estimated_endtime=Decimal('4680'), additional_cost=Decimal('1080'), task=Task(goal=Goal(predicate=('rescued', 'civ5'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('1')), Goal(predicate=('rescued', 'civ11'), deadline=Decimal('Infinity')): Bid(agent='medic0', estimated_endtime=Decimal('960'), additional_cost=Decimal('960'), task=Task(goal=Goal(predicate=('rescued', 'civ11'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('1')), Goal(predicate=('rescued', 'civ1'), deadline=Decimal('Infinity')): Bid(agent='medic1', estimated_endtime=Decimal('960'), additional_cost=Decimal('360'), task=Task(goal=Goal(predicate=('rescued', 'civ1'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('1')), Goal(predicate=('rescued', 'civ4'), deadline=Decimal('Infinity')): Bid(agent='medic1', estimated_endtime=Decimal('3600'), additional_cost=Decimal('960'), task=Task(goal=Goal(predicate=('rescued', 'civ4'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('1')), Goal(predicate=('rescued', 'civ2'), deadline=Decimal('Infinity')): Bid(agent='medic1', estimated_endtime=Decimal('2640'), additional_cost=Decimal('840'), task=Task(goal=Goal(predicate=('rescued', 'civ2'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('1')), Goal(predicate=('rescued', 'civ0'), deadline=Decimal('Infinity')): Bid(agent='medic1', estimated_endtime=Decimal('600'), additional_cost=Decimal('600'), task=Task(goal=Goal(predicate=('rescued', 'civ0'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('0.086')), Goal(predicate=('rescued', 'civ6'), deadline=Decimal('Infinity')): Bid(agent='medic0', estimated_endtime=Decimal('2400'), additional_cost=Decimal('1080'), task=Task(goal=Goal(predicate=('rescued', 'civ6'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('1')), Goal(predicate=('rescued', 'civ9'), deadline=Decimal('Infinity')): Bid(agent='medic0', estimated_endtime=Decimal('3600'), additional_cost=Decimal('1200'), task=Task(goal=Goal(predicate=('rescued', 'civ9'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('1')), Goal(predicate=('rescued', 'civ10'), deadline=Decimal('Infinity')): Bid(agent='medic1', estimated_endtime=Decimal('1800'), additional_cost=Decimal('840'), task=Task(goal=Goal(predicate=('rescued', 'civ10'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('1')), Goal(predicate=('rescued', 'civ3'), deadline=Decimal('Infinity')): Bid(agent='medic0', estimated_endtime=Decimal('1320'), additional_cost=Decimal('360'), task=Task(goal=Goal(predicate=('rescued', 'civ3'), deadline=Decimal('Infinity')), value=Decimal('100000')), requirements=(), computation_time=Decimal('1'))}
        computation_time = Decimal(10)

        return sorted(allocation.values(), key=attrgetter("task.goal.deadline")), computation_time
        # to here
        while tasks:
            task = Task.combine(tasks.pop_equal())

            if task.goal in allocation:
                # there is already already an agent assigned to this goal (and deadline)
                raise NotImplementedError("Not sure this is correct or even possible")
                current_bid = allocation[task.goal]
                new_bid = current_bid._replace(task=Task.combine([current_bid.task, task]))
                allocation[task.goal] = new_bid
                continue

            bids = [e.generate_bid(task, self.planner, model, time, self.event_executor.known_events)
                    for e in self._executors]
            bids = [b for b in bids if b is not None]  # filter out failed bids

            if not bids:
                continue
                # raise ValueError("no bids for {}".format(task))

            # parallel computation -- only take longest
            computation_time += max(b.computation_time for b in bids)
            winning_bid = min(bids, key=attrgetter("additional_cost"))

            # notify winner of winning bid
            allocation[winning_bid.task.goal] = winning_bid
            self.executor_by_name(winning_bid.agent).notify_bid_won(winning_bid)

            # add additional goals if not already met
            tasks.extend(winning_bid.requirements)

        result = sorted(allocation.values(), key=attrgetter("task.goal.deadline")), computation_time
        log.info(result[0])
        return result

    def notify_goal_realisation(self, events: "list[Event]"):
        self.event_executor.agent_based_events.extend(events)
