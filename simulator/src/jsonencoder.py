from functools import partial
from simplejson import JSONEncoder, dumps

from action import Action
from roborescue.event import Event

__author__ = 'jack'
__all__ = ["json_dumps", "ActionEncoder"]


class ActionEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Action):
            d = dict(type=type(o).__name__, **vars(o))
            d.pop("apply", None)  # remove monkey patched partial apply if it exists
            d.pop("tils", None)  # remove extraneaous information associated with planning
            d.pop("goals", None)
            d.pop("plan", None)
            d.pop("metric", None)
            return d
        elif isinstance(o, Event):
            d = dict(vars(o), id=o.id_, type=o.type)
            d.pop("id_")
            return d
        return super().default(o)


json_dumps = partial(dumps, cls=ActionEncoder)
