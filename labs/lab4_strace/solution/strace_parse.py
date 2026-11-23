#!/usr/bin/env python3
"""Lab 4 solution, part 2: turn a raw strace log into structured events and a summary.

    python3 strace_parse.py raw_strace.log --out events.jsonl
    python3 strace_parse.py sample/strace_sample.log          # works without a phone
"""
import argparse
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

# One strace line looks like:
#   9764  17:14:15.980564 openat(AT_FDCWD, "/data/.../note.txt", O_WRONLY|O_CREAT, 0600) = 55
#   pid   time            syscall(arguments ...........................................) = result
LINE = re.compile(r"^(\d+)\s+(\d\d:\d\d:\d\d\.\d+)\s+(\w+)\((.*)\)\s+=\s+(-?\d+|\?)\s*(.*)$")


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def category_map(config):
    """{"openat": "filesystem", "connect": "network", ...}"""
    mapping = {}
    for category, syscalls in config["categories"].items():
        for name in syscalls:
            mapping[name] = category
    return mapping


def target_of(syscall, args):
    """The interesting part of a call: a path, an address:port, or a program."""
    if syscall == "connect":
        m = re.search(r'sun_path="([^"]*)"', args)          # a local (unix) socket
        if m:
            return m.group(1)
        port = re.search(r"sin6?_port=htons\((\d+)\)", args)
        addr = re.search(r'(?:inet_pton\(AF_INET6, |inet_addr\()"([^"]*)"', args)
        if port and addr:
            ip = addr.group(1).replace("::ffff:", "")       # IPv4 written inside IPv6
            return "%s:%s" % (ip, port.group(1))
        return ""
    m = re.search(r'"([^"]*)"', args)                        # first quoted text = path / program
    return m.group(1) if m else ""


def parse_line(line, categories):
    """One raw line -> one event dict, or None if the line is not a finished call."""
    m = LINE.match(line.strip())
    if not m:
        return None            # "+++ exited", "--- SIGCHLD", "<unfinished ...>" ...
    pid, time_, syscall, args, result, rest = m.groups()
    error = rest.split()[0] if result == "-1" and rest else None
    return {
        "time": time_,
        "pid": int(pid),
        "syscall": syscall,
        "category": categories.get(syscall, "other"),
        "target": target_of(syscall, args),
        "args": args,
        "result": result,
        "error": error,
        "ok": result != "-1",
    }


def add_highlights(event, config):
    event["highlights"] = [
        h["label"] for h in config.get("highlights", [])
        if event["syscall"] in h["syscalls"] and re.search(h["pattern"], event["target"])
    ]


def load_events(path, config):
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

    print("== Calls by category ==")
    for category, n in Counter(e["category"] for e in events).most_common():
        print("%-12s %d" % (category, n))

    failed = [e for e in events if not e["ok"]]
    print("\n== Failed calls: %d (a failure is often a file the app looked for and did not find) ==" % len(failed))
    for name, n in Counter("%s -> %s" % (e["syscall"], e["error"]) for e in failed).most_common(5):
        print("%5d  %s" % (n, name))

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
        if len(seen) > 8:
            print("   ... and %d more" % (len(seen) - 8))


def main():
    p = argparse.ArgumentParser(description="Lab 4: parse a raw strace log")
    p.add_argument("log")
    p.add_argument("--config", default=os.path.join(HERE, "strace_config.json"))
    p.add_argument("--out", default=None, help="write events as JSON Lines to this file")
    args = p.parse_args()

    config = load_config(args.config)
    events = load_events(args.log, config)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
        print("[+] %d events -> %s\n" % (len(events), os.path.abspath(args.out)))

    print_summary(events, config)


if __name__ == "__main__":
    main()
