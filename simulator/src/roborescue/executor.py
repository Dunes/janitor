

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

    @property
    def known_events(self):
        return [e for e in self.events if not e.hidden]

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

    @staticmethod
    @abstractmethod
    def extract_goals(plan):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def extract_events(plan, time):
        raise NotImplementedError

    def halt(self, time):
        """halt all actions at current time"""
        log.debug("halting {}", self.agent)
        self.halted = True
        self.plan = []
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
        # for action_ in plan:
        #     if isinstance(action_, Rescue) and action_.target not in rescued:
        #         goals.append(["unburied", action_.target])
        #         rescued.add(action_.target)

        return goals

    @staticmethod
    def extract_events(plan, time):
        return []


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
        if not any(self.EXECUTORS[id_].has_goals for id_ in self.executor_ids):
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
        self.executing = ActionState(plan_action, plan_action.start_time).start()

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


