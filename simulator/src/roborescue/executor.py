__author__ = 'jack'

from logging import getLogger
from operator import attrgetter
from decimal import Decimal
from itertools import count, groupby
from weakref import WeakValueDictionary
from abc import abstractmethod, ABCMeta

from .action import Plan, LocalPlan, Observe, Move, Unblock, Unload, Rescue, EventAction
from action_state import ActionState, ExecutionState
from logger import StyleAdapter
from planning_exceptions import ExecutionError, NoPlanException
from accuracy import as_start_time, as_next_end_time, zero


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
    def __init__(self, *, events):
        super().__init__(agent="event_executor", planning_time=None, deadline=None)
        time = attrgetter("time")
        events = sorted(events, key=time)
        event_actions = []
        for t, evts in groupby(events, key=time):
            event_actions.append(EventAction(time=t, events=tuple(evts)))
        self.event_actions = event_actions
        self.events = events

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
        action_state.action.apply(model)
        for e in action_state.action.events:
            self.events.remove(e)

    def notify_action_finishing(self, action_state: ActionState, model):
        super().notify_action_finishing(action_state, model)
        assert self.executing is action_state
        action_state.finish()
        self.executing = None

    def notify_new_knowledge(self, time, node):
        pass


class AgentExecutor(Executor):

    def __init__(self, *, agent, planning_time, plan=None, deadline=Decimal("Infinity"), planner_id=None,
                 halted=False):
        super().__init__(agent=agent, planning_time=planning_time, deadline=deadline)
        self.plan = plan or []
        self.planner_id = planner_id
        self.halted = halted

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
            planner = self.EXECUTORS[self.planner_id].local_planner
            action_ = action_state.action
            try:
                new_plan, time_taken = planner.get_plan_and_time_taken(
                    model, duration=planner.planning_time, agent=self.agent, goals=action_.goals,
                    metric=None, time=action_state.time, events=action_.events)
                plan_action = action_.copy_with(plan=new_plan, duration=zero)
                self.executing = ActionState(plan_action, plan_action.start_time).start()
            except NoPlanException:
                self.EXECUTORS[self.planner_id].notify_planning_failure(self.id, action_state.time)
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
                self.EXECUTORS[self.planner_id].notify_new_knowledge(action_state.time, changes)

    def notify_new_knowledge(self, time, changes):
        for change in changes:
            for action_ in self.plan:
                if action_.is_effected_by_change(change):
                    goals = self.extract_goals(self.plan)
                    events = self.extract_events(self.plan, as_start_time(time))
                    assert goals
                    self.halt(time)
                    self.new_plan([LocalPlan(as_start_time(time), self.planning_time, self.agent, goals=goals,
                                           events=events)])
                    break

    def new_plan(self, plan):
        self.plan = plan
        self.halted = False

    @staticmethod
    @abstractmethod
    def extract_goals(plan):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def extract_events(plan, time):
        raise NotImplementedError

    def halt(self, time):
        """halt all actions are current time"""
        log.debug("halting {}", self.agent)
        self.halted = True
        self.plan = []
        if self.executing and not isinstance(self.executing.action, Observe):
            log.debug("halting {} at {}", self.executing.action, time)
            if self.executing.action.start_time == time:
                # action never started
                self.executing = None
            else:
                new_action = self.executing.action.as_partial(end_time=time)
                if new_action.start_time != self.executing.action.start_time:
                    assert False
                self.executing = ActionState(new_action).start()


class PoliceExecutor(AgentExecutor):

    @staticmethod
    def extract_goals(plan):
        goals = []
        for action_ in plan:
            if isinstance(action_, Unblock):
                goals.append(["edge", action_.start_node, action_.end_node])
        return goals

    @staticmethod
    def extract_events(plan, time):
        return []


class MedicExecutor(AgentExecutor):

    @staticmethod
    def extract_goals(plan):
        goals = []
        rescued = set()
        for action_ in plan:
            if isinstance(action_, Unload) and action_.target not in rescued:
                goals.append(["rescued", action_.target])
                rescued.add(action_.target)
        for action_ in plan:
            if isinstance(action_, Rescue) and action_.target not in rescued:
                goals.append(["unburied", action_.target])
                rescued.add(action_.target)

        return goals

    @staticmethod
    def extract_events(plan, time):
        return []


class CentralPlannerExecutor(Executor):

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
    def deadline(self):
        return self._deadline

    @deadline.setter
    def deadline(self, deadline):
        if self.executing:
            raise ExecutionError("Wasn't expecting to be told deadline is changing when already planning")
        self._deadline = deadline

    @property
    def has_goals(self):
        return not self.valid_plan

    def next_action(self, time):
        assert not self.valid_plan
        if self.executing:
            return self.executing
        return ActionState(Plan(as_start_time(time), self.planning_time))

    def notify_action_starting(self, action_state: ActionState, model):
        assert not self.executing

        if not isinstance(action_state.action, Plan):
            raise ExecutionError("Have a non-plan action: " + str(action_state.action))

        new_plan, time_taken = self.central_planner.get_plan_and_time_taken(
            model, duration=self.central_planner.planning_time, agent="all", goals=model["goal"],
            metric=model["metric"], time=action_state.time, events=self.event_executor.events
        )
        new_plan = self.adjust_plan(new_plan)
        plan_action = action_state.action.copy_with(plan=new_plan, duration=time_taken)
        self.executing = ActionState(plan_action, plan_action.start_time).start()

    def notify_action_finishing(self, action_state: ActionState, model):
        super().notify_action_finishing(action_state, model)
        assert self.executing is action_state
        self.executing = None
        action_state = action_state.finish()
        plan = action_state.action.apply(model)

        # disseminate plan
        for agent, sub_plan in self.disseminate_plan(plan):
            self.EXECUTORS[self.agent_executor_map[agent]].new_plan(list(sub_plan))

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
    def disseminate_plan(plan):
        plan = sorted(plan, key=attrgetter("agent", "start_time"))
        return groupby(plan, key=attrgetter("agent"))


