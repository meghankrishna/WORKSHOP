#!/usr/bin/env python3
"""Lab 3 starter: summarise a monitor.jsonl log.

    python3 summarize.py monitor.jsonl --apis apis.json
"""
import argparse
import json
from collections import Counter


def load_records(path):
    # TODO 1: read the JSON Lines file; skip blank lines and lines that are not
    # valid JSON (the monitor may have been killed mid-write). Return a list of dicts.
    raise NotImplementedError


def main():
    p = argparse.ArgumentParser()
    p.add_argument("log")
    p.add_argument("--apis", help="apis.json, to report configured APIs that never fired")
    args = p.parse_args()

    records = load_records(args.log)
    print(f"{len(records)} calls recorded\n")

    # TODO 2: print "== Calls by category ==" (Counter over record["category"]),
    #         most common first.
    # TODO 3: print "== Top APIs ==" (Counter over "class.method"), top 10.
    # TODO 4: print "== Exceptions ==": every record whose "exception" is set.
    # TODO 5: if --apis was given, print "== Configured APIs that never fired =="
    #         by comparing the config's (class, method) pairs with the log.
    #         Note a config "method" can be a string or a list.


if __name__ == "__main__":
    main()
