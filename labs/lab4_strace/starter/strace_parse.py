#!/usr/bin/env python3
"""Lab 4, part 2: turn a raw strace log into structured events and a summary.

You can work on this part WITHOUT a phone, using the sample log:

    python3 strace_parse.py ../solution/sample/strace_sample.log --out events.jsonl
"""
import argparse
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

# One strace line looks like:
#   9764  17:14:15.980564 openat(AT_FDCWD, "/data/.../note.txt", O_WRONLY|O_CREAT, 0600) = 55
#   pid   time            syscall(arguments ..................................) = result
# This pattern PROVIDED FOR YOU splits it into six pieces:
#   pid, time, syscall, arguments, result, rest-of-line (e.g. "ENOENT (No such file...)")
LINE = re.compile(r"^(\d+)\s+(\d\d:\d\d:\d\d\.\d+)\s+(\w+)\((.*)\)\s+=\s+(-?\d+|\?)\s*(.*)$")


def load_config(path):
    """PROVIDED."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def category_map(config):
    """PROVIDED. {"openat": "filesystem", "connect": "network", ...}"""
    mapping = {}
    for category, syscalls in config["categories"].items():
        for name in syscalls:
            mapping[name] = category
    return mapping


def target_of(syscall, args):
    """The interesting part of a call: a path, an 'address:port', or a program."""
    # TODO 2: return the target as text.
    #   - for "connect":
    #       * a local socket has  sun_path="/dev/socket/dnsproxyd"  -> return that path
    #         hint: re.search(r'sun_path="([^"]*)"', args)
    #       * an internet connection has  sin6_port=htons(443)  and  inet_pton(AF_INET6, "::ffff:1.2.3.4", ...)
    #         -> return "1.2.3.4:443"   (remove the "::ffff:" part)
    #         hints: re.search(r"sin6?_port=htons\((\d+)\)", args)
    #                re.search(r'inet_pton\(AF_INET6, "([^"]*)"', args)
    #   - for everything else (openat, faccessat, execve ...): the FIRST text in quotes
    #       hint: re.search(r'"([^"]*)"', args)
    #   - return "" if nothing is found
    raise NotImplementedError


def parse_line(line, categories):
    """One raw line -> one event (a dict), or None if the line is not a finished call."""
    m = LINE.match(line.strip())
    if not m:
        return None            # lines like "+++ exited", "--- SIGCHLD ---" are skipped
    pid, time_, syscall, args, result, rest = m.groups()

    # TODO 1: build and return a dict with these keys:
    #   "time"     the time text
    #   "pid"      the pid as a number (int)
    #   "syscall"  e.g. "openat"
    #   "category" categories.get(syscall, "other")
    #   "target"   target_of(syscall, args)
    #   "args"     the arguments text
    #   "result"   the result text
    #   "error"    the error name, e.g. "ENOENT": the first word of `rest`,
    #              but only when result == "-1"; otherwise None
    #   "ok"       True unless result == "-1"
    raise NotImplementedError


def add_highlights(event, config):
    """PROVIDED. Mark events that match a rule from the config's "highlights" list."""
    event["highlights"] = [
        h["label"] for h in config.get("highlights", [])
        if event["syscall"] in h["syscalls"] and re.search(h["pattern"], event["target"])
    ]


def load_events(path, config):
    """PROVIDED. Read the raw log and return the list of events."""
    categories = category_map(config)
    events = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            event = parse_line(line, categories)
            if event:
                add_highlights(event, config)
                events.append(event)
    return events


def print_summary(events, config):
    print("%d system calls recorded\n" % len(events))

    # TODO 3: print "== Calls by category ==" and then one line per category with its
    #         count, most common first.
    #         hint: Counter(e["category"] for e in events).most_common()

    # TODO 4: print how many calls FAILED (e["ok"] is False) and the 5 most common
    #         failures as "syscall -> error", e.g. "faccessat -> ENOENT".
    #         A failure is often a file the app looked for and did not find.

    # PROVIDED: for each highlight rule, list the distinct targets it matched.
    notes = {h["label"]: h["note"] for h in config.get("highlights", [])}
    for label in notes:
        hits = [e for e in events if label in e["highlights"]]
        if not hits:
            continue
        print("\n== %s (%d)  %s ==" % (label, len(hits), notes[label]))
        seen = []
        for e in hits:
            entry = e["target"] + ("" if e["ok"] else "   [failed: %s]" % e["error"])
            if entry not in seen:
                seen.append(entry)
        for entry in seen[:8]:
            print("   " + entry)


def main():
    p = argparse.ArgumentParser(description="Lab 4: parse a raw strace log")
    p.add_argument("log")
    p.add_argument("--config", default=os.path.join(HERE, "strace_config.json"))
    p.add_argument("--out", default=None, help="write events as JSON Lines to this file")
    args = p.parse_args()

    config = load_config(args.config)
    events = load_events(args.log, config)

    if args.out:
        # TODO 5: write the events to args.out as JSON Lines: ONE json.dumps(event) per
        #         line (same idea as Lab 3). Make sure the folder exists first, then print
        #         how many events were written.
        pass

    print_summary(events, config)


if __name__ == "__main__":
    main()
