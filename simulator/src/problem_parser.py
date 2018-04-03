import simplejson
from markettaskallocation.common.event import decode_event
from decimal import Decimal
from jsonencoder import ActionEncoder

__all__ = ["decode", "encode"]


def decode(filename):
    with open(filename) as fh:
        obj = simplejson.load(fh, use_decimal=True, parse_int=Decimal)
    if "events" in obj:
        obj["events"] = [decode_event(e) for e in obj["events"]]
    return obj


def encode(filename, obj, **kwargs):
    with open(filename, mode="w") as fh:
        simplejson.dump(obj, fh, use_decimal=True, cls=ActionEncoder, **kwargs)
