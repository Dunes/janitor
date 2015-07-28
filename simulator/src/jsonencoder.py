__author__ = 'jack'

from functools import partial

from simplejson import JSONEncoder, dumps

from action import Action

__all__ = ["json_dumps", "ActionEncoder"]


class ActionEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Action):
            d = dict(type=type(o).__name__, **vars(o))
            d.pop("apply", None)  # remove monkey patched partial apply if it exists
            d.pop("tils", None)  # remove extraneaous information associated with planning
            d.pop("goals", None)
            d.pop("plan", None)
            return d
        return super().default(o)


json_dumps = partial(dumps, cls=ActionEncoder)
