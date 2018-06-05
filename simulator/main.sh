#! /bin/bash
export PYTHONPATH="src"
export PYTHONHASHSEED=1  # make str hashes (for dicts) repeatable across different invocations of the program
./main.py "$@"
