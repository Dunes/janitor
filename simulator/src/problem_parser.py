import simplejson
from roborescue.event import Event


def decode(filename):
    with open(filename) as fh:
        obj = simplejson.load(fh, use_decimal=True)
    if "events" in obj:
        obj["events"] = [Event(**e) for e in obj["events"]]
    return obj


def encode(filename, obj):
    with open(filename, mode="w") as fh:
        simplejson.dump(obj, fh, use_decimal=True)
