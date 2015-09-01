__author__ = 'jack'

from .problem_encoder import find_object, create_predicate, unknown_value_getter


class Event:

    def __init__(self, time, object_id, predicate, becomes=True):
        self.time = time
        self.object_id = object_id
        self.predicate = predicate
        self.becomes = becomes

    def as_predicate(self, time, model):
        if time > self.time:
            raise ValueError("{} has expired. Current time: {}".format(self, time))
        if self.becomes is False:
            obj = find_object_or_edge(self.object_id, model)
            if "known" not in obj:
                predicate_value = obj[self.predicate]
            else:
                predicate_value = obj["known"].get(self.predicate)
                if predicate_value is None:
                    assert isinstance(obj["unknown"][self.predicate]["actual"], bool)
                    predicate_value = unknown_value_getter(obj["unknown"], self.predicate, model["assumed-values"])
                    if predicate_value is False:
                        return None
            predicate = "not", create_predicate(self.predicate, predicate_value, self.object_id)
        else:
            predicate = create_predicate(self.predicate, self.becomes, self.object_id)

        return "at", self.time - time, predicate

    def __repr__(self):
        return "Event(time={time}, object_id={object_id!r}, predicate={predicate!r}, becomes={becomes!r})" \
            .format_map(vars(self))


def find_object_or_edge(id_, model):
    if " " not in id_:
        return find_object(id_, model["objects"])
    else:
        return find_edge(id_, model["graph"])


def find_edge(edge_id, graph):
    try:
        return graph["edges"][edge_id]
    except KeyError:
        if not graph.get("bidirectional"):
            raise
    reverse_id = " ".join(reversed(edge_id.split(" ")))
    return graph["edges"][reverse_id]