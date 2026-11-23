#!/usr/bin/env python3
"""Lab 3 solution: summarise a monitor.jsonl log.

    python3 summarize.py monitor.jsonl --apis apis.json
"""
import argparse
import json
from collections import Counter


def load_records(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                pass  # truncated last line if the monitor was killed mid-write
    return records


def configured_pairs(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    pairs = []
    for h in cfg.get("hooks", []):
        m = h.get("method", h.get("methods", []))
        for name in ([m] if isinstance(m, str) else m):
            pairs.append((h["class"], name))
    return pairs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("log")
    p.add_argument("--apis", help="apis.json, to report configured APIs that never fired")
    args = p.parse_args()

    records = load_records(args.log)
    print(f"{len(records)} calls recorded\n")

    print("== Calls by category ==")
    for cat, n in Counter(r.get("category", "?") for r in records).most_common():
        print(f"{cat:<20}{n}")

    print("\n== Top APIs ==")
    api = Counter(f"{r.get('class')}.{r.get('method')}" for r in records)
    for name, n in api.most_common(10):
        print(f"{n:>6}  {name}")

    print("\n== Exceptions ==")
    exc = [r for r in records if r.get("exception")]
    if not exc:
        print("none")
    for r in exc:
        print(f"{r['class']}.{r['method']}: {r['exception']}")

    if args.apis:
        seen = {(r.get("class"), r.get("method")) for r in records}
        missing = [f"{c}.{m}" for c, m in configured_pairs(args.apis) if (c, m) not in seen]
        print("\n== Configured APIs that never fired ==")
        print("\n".join(missing) if missing else "none (all configured APIs fired)")


if __name__ == "__main__":
    main()
