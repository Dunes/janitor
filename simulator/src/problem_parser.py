import simplejson


def decode(filename):
    with open(filename) as fh:
        obj = simplejson.load(fh, use_decimal=True)
    return obj


def encode(filename, obj):
    with open(filename, mode="w") as fh:
        simplejson.dump(obj, fh, use_decimal=True)
