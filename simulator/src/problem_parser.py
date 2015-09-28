import simplejson
from roborescue.event import Event
from decimal import Decimal


def decode(filename):
    with open(filename) as fh:
        obj = simplejson.load(fh, use_decimal=True, parse_int=Decimal)
    if "events" in obj:
        obj["events"] = [Event(**e) for e in obj["events"]]
    return obj


def encode(filename, obj, **kwargs):
    with open(filename, mode="w") as fh:
        simplejson.dump(obj, fh, use_decimal=True, **kwargs)
