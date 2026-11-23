#!/usr/bin/env python3
"""Lab 3 starter: host-side runner for the Frida API monitor.

    python3 run_monitor.py <package> --apis apis.json --duration 60 --out monitor.jsonl
"""
import argparse
import json
import os
import sys
import threading
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))


def build_agent(js_path):
    """Compile agent.js together with frida-java-bridge (needed by Frida 17+)."""
    folder = os.path.dirname(os.path.abspath(js_path))
    root = None
    while True:  # look upward for node_modules/frida-java-bridge
        if os.path.isdir(os.path.join(folder, "node_modules", "frida-java-bridge")):
            root = folder
            break
        parent = os.path.dirname(folder)
        if parent == folder:
            break
        folder = parent
    if root is None:
        sys.exit("[-] frida-java-bridge not found. Ask your instructor (it should be installed).")
    return frida.Compiler().build(os.path.abspath(js_path), project_root=root)


def find_pid(device, package):
    """Frida lists apps by their display label (e.g. "Settings"), not by package
    name, so look the running app up by its identifier instead."""
    for app in device.enumerate_applications():
        if app.identifier == package and app.pid:
            return app.pid
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("package")
    p.add_argument("--apis", default=os.path.join(HERE, "apis.json"))
    p.add_argument("--agent", default=os.path.join(HERE, "agent.js"))
    p.add_argument("--out", default="monitor.jsonl")
    p.add_argument("--duration", type=int, default=60)
    p.add_argument("--attach", action="store_true", help="attach to a running app instead of spawning")
    args = p.parse_args()

    with open(args.apis) as f:
        config = json.load(f)

    # TODO 1: open args.out for writing (JSON Lines: one json.dumps(record) + "\n" per call).
    # Protect writes with a threading.Lock -- messages arrive on another thread.

    def on_message(message, data):
        # TODO 2: handle message["type"] == "send": the payload is either an
        # {"event": ...} dict ("ready"/"warn"/"fatal": print it) or a call
        # record (write it to the file and print a one-line summary).
        # Also print message["type"] == "error" descriptions.
        pass

    # TODO 3: get the device (frida.get_usb_device(timeout=10)), then either
    #   attach(find_pid(device, args.package))   when --attach
    #       (find_pid is provided above: Frida names apps by label, not package)
    #   spawn([args.package]) + attach(pid)  otherwise
    # create_script(build_agent(args.agent)), connect on_message, load(),
    # call script.exports_sync.init(config) BEFORE device.resume(pid),
    # then sleep args.duration seconds.
    # TODO 4: in a finally block unload the script, detach, close the file and
    # print how many calls were recorded.
    raise NotImplementedError


if __name__ == "__main__":
    main()
