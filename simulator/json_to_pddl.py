#! /usr/bin/python3

import sys
import pathlib

src = pathlib.Path("./src").resolve()
if not any(pathlib.Path(p).resolve() == src for p in sys.path):
    sys.path.append(str(src))

import argparse
from markettaskallocation.common.problem_encoder import encode_problem_to_file
from problem_parser import decode


def parser():
    p = argparse.ArgumentParser(description="Turns json problems into pddl files")
    p.add_argument("--model", "-m")
    p.add_argument("--out", "-o")
    return p


def main(model, out):
    model = decode(model)
    encode_problem_to_file(
        filename=out,
        model=model,
        agent="all",
        goals=model["goal"],
        metric=model["metric"],
        time=0,
        events=model["events"]
    )


if __name__ == "__main__":
    args = parser().parse_args()
    main(args.model, args.out)

