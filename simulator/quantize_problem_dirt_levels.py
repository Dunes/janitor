"""Converts model files to use only integer values for dirtiness. Rounds to the nearest even number for extra dirty rooms"""

import os.path
from simplejson import load, dump
from itertools import chain
from decimal import Decimal

folder_sq = "problems/no-stock-4x4"
folder_rect = "problems/no-stock-rect16"

def quantize_node_dirtiness(model):
    def round_even(d):
        res = d.quantize(0)
        if res % 2 != 0:
            if res < d:
                res += 1
            else:
                res -= 1
        return res

    for name, value in model["nodes"].items():
        if "unknown" not in value:
            continue
        dirt_value = value["unknown"]["dirtiness"]
        
        if not isinstance(dirt_value["actual"], Decimal):
            raise TypeError(type(dirt_value["actual"]))
        
        if "rm-ed" in name:
            dirt_value["actual"] = round_even(dirt_value["actual"])
        elif "rm" in name:
            dirt_value["actual"] = dirt_value["actual"].quantize(0)

def run():
    for directory, _dirs, files in chain(os.walk(folder_sq), os.walk(folder_rect)):
        for name in files:
            relpath = os.path.join(directory, name)
            with open(relpath) as f:
                model = load(f, use_decimal=True)
            
            try:
                quantize_node_dirtiness(model)
            except Exception:
                print("problem file:", name)
                raise
            
            with open(relpath, "w") as f:
                dump(model, f, use_decimal=True)

if __name__ == "__main__":
    run()
