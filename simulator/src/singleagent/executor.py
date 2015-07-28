__author__ = 'jack'

from logging import getLogger
from operator import attrgetter
from decimal import Decimal
from itertools import count, groupby
from weakref import WeakValueDictionary
from abc import abstractmethod, ABCMeta

from janitor.action import Plan, LocalPlan, Observe, Move, Clean, ExtraClean, ExtraCleanPart
from action_state import ActionState, ExecutionState
from logger import StyleAdapter
from planning_exceptions import ExecutionError, NoPlanException
from pddl_parser import CleaningWindowTil
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
    def adjust_plan(cls, plan, start_time):
        return sorted(cls._adjust_plan_helper(plan, start_time), key=attrgetter("start_time", "_ordinal"))

    @staticmethod
    def _adjust_plan_helper(plan, start_time):
        for action in plan:
            # adjust for OPTIC starting at t = 0
            action = action.copy_with(start_time=action.start_time + start_time)
            yield action
            if type(action) is Move:
                yield Observe(action.end_time, action.agent, action.end_node)


class AgentExecutor(Executor):

    def __init__(self, *, agent, planning_time, plan=None, deadline=Decimal("Infinity"), planner_id=None,
                 halted=False):
        super().__init__(agent=agent, planning_time=planning_time, deadline=deadline)
        self.plan = plan or []
        self.planner_id = planner_id
        self.halted = halted

    def copy(self):
        raise NotImplementedError
        log.debug("Executor.copy()")

    @property
    def deadline(self):
        return self._deadline

    @deadline.setter
    def deadline(self, deadline):
        raise NotImplementedError
        self._deadline = deadline
        if self.executing:
            new_action = self.executing.action.as_partial(deadline)
            if not new_action:
                raise ExecutionError("executing action does not want to partially complete")
            self.executing = ActionState(new_action, deadline, ExecutionState.executing)
        new_plan = []
        for a in self.plan:
            if a.end_time <= deadline:
                new_plan.append(a)
            else:
                partial_action = a.as_partial(deadline)
                if partial_action:
                    new_plan.append(partial_action)
                break
        # halt?
        self.new_plan(new_plan)

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
                    model, agent=self.agent, goals=action_.goals, tils=action_.tils)
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
            self.new_plan(self.adjust_plan(action_state.action.apply(model),
                                         start_time=as_start_time(action_state.time)))
        elif action_state.action.apply(model):
            # new knowledge
            self.EXECUTORS[self.planner_id].notify_new_knowledge(action_state.time, action_state.action.node)

    def notify_new_knowledge(self, time, node):
        for action_ in self.plan:
            if isinstance(action_, (Clean, ExtraCleanPart)) and action_.room == node:
                goals = self.extract_goals(self.plan)
                tils = self.extract_tils(self.plan, as_start_time(time))
                assert goals
                self.halt(time)
                self.new_plan([LocalPlan(as_start_time(time), self.planning_time, self.agent, goals=goals,
                                       tils=tils)])
                break

    def new_plan(self, plan):
        self.plan = plan
        self.halted = False

    @staticmethod
    def extract_goals(plan):
        return [["cleaned", action_.room]
                for action_ in plan if isinstance(action_, (Clean, ExtraCleanPart))]

    @staticmethod
    def extract_tils(plan, time):
        tils = []
        for action_ in plan:
            if isinstance(action_, ExtraCleanPart):
                tils.append(CleaningWindowTil(action_.start_time - time, action_.room, True))
                tils.append(CleaningWindowTil(as_next_end_time(action_.end_time - time), action_.room, False))
        return tils

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


class CentralPlannerExecutor(Executor):

    def __init__(self, *, agent, planning_time, executor_ids, agent_names, deadline=Decimal("Infinity"),
                 central_planner, local_planner):
        super().__init__(agent=agent, planning_time=planning_time, deadline=deadline)
        self.valid_plan = False
        self.central_planner = central_planner
        self.local_planner = local_planner
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

        new_plan, time_taken = self.central_planner.get_plan_and_time_taken(model)
        new_plan = self.adjust_plan(new_plan, action_state.time + time_taken)
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

    @classmethod
    def disseminate_plan(cls, plan):
        plan = sorted(cls.replace_extra_clean_actions(plan), key=attrgetter("agent", "start_time"))
        return groupby(plan, key=attrgetter("agent"))

    @staticmethod
    def replace_extra_clean_actions(plan):
        for action_ in plan:
            if isinstance(action_, ExtraClean):
                for agent in action_.agents():
                    yield ExtraCleanPart(action_.start_time, action_.duration, agent, action_.room)
            else:
                yield action_
