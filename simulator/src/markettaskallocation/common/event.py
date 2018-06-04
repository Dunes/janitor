from logging import getLogger
from logger import StyleAdapter
from abc import ABCMeta, abstractmethod
from collections import namedtuple

from markettaskallocation.common.problem_encoder import find_object, create_predicate


log = StyleAdapter(getLogger(__name__))
__author__ = 'jack'


class Predicate:
    def __init__(self, name, becomes, was=None):
        self.name = name
        self.becomes = becomes
        self.was = was


class Event(metaclass=ABCMeta):

    def __init__(self, time, id_, predicates, hidden=False, external=True):
        self.time = time
        self.id_ = id_
        self.predicates = predicates
        self.hidden = hidden
        self.external = external

    @abstractmethod
    def find_object(self, model):
        raise NotImplementedError

    def get_predicates(self, time, model):
        if time > self.time:
            raise ValueError("{} has expired. Current time: {}".format(self, time))
        if self.hidden:
            raise TypeError("{} is hidden".format(self))

        pddl_predicates = []
        for p in self.predicates:
            if p.becomes is False:
                if p.was is not None:
                    predicate_value = p.was
                else:
                    obj = self.find_object(model)
                    predicate_value = obj["known"][p.name]
                predicate = "not", create_predicate(p.name, predicate_value, self.id_)
            else:
                predicate = create_predicate(p.name, p.becomes, self.id_)

            pddl_predicates.append(("at", self.time - time, predicate))
        return pddl_predicates

    def apply(self, model):
        obj = self.find_object(model)
        values = obj["known"]
        for p in self.predicates:
            values[p.name] = p.becomes
        return self.id_

    def __repr__(self):
        return "Event(time={time}, id_={id_!r}, predicates={predicates}, hidden={hidden}, external={external})" \
            .format_map(vars(self))


class ObjectEvent(Event):
    type = "object"

    def find_object(self, model):
        return find_object(self.id_, model["objects"])


class EdgeEvent(Event):
    type = "edge"

    def find_object(self, model):
        return model["graph"]["edges"][self.id_]


def decode_event(attributes: dict) -> Event:
    predicates = [Predicate(**p) for p in attributes["predicates"]]
    type_name = attributes["type"]
    if type_name == "object":
        return ObjectEvent(attributes["time"], attributes["id"], predicates, attributes.get("hidden", False))
    elif type_name == "edge":
        return EdgeEvent(attributes["time"], attributes["id"], predicates, attributes.get("hidden", False))
    else:
        raise ValueError("unknown event type: " + type_name)
