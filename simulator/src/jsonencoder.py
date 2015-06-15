__author__ = 'jack'

from simplejson import JSONEncoder, dumps
from action import Action
from functools import partial

__all__ = ["json_dumps", "ActionEncoder"]


class ActionEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Action):
            d = dict(type=type(o).__name__, **vars(o))
            d.pop("apply", None)  # remove monkey patched partial apply if it exists
            return d
        return super().default(o)


json_dumps = partial(dumps, cls=ActionEncoder)
