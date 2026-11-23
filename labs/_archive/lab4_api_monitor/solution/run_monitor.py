#!/usr/bin/env python3
"""Lab 3 solution: host-side runner for the Frida API monitor.

    python3 run_monitor.py <package> --apis apis.json --duration 60 --out monitor.jsonl
"""
import argparse
import datetime
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
    p.add_argument("--attach", action="store_true",
                   help="attach to a running app instead of spawning")
    args = p.parse_args()

    with open(args.apis) as f:
        config = json.load(f)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    fh = open(args.out, "w", encoding="utf-8")
    lock = threading.Lock()
    count = [0]
    stop = threading.Event()

    def on_message(message, data):
        t = message.get("type")
        if t == "send":
            payload = message.get("payload")
            if isinstance(payload, dict) and "event" in payload:
                ev = payload["event"]
                if ev == "ready":
                    print("[+] hooks installed: %d methods across %d classes"
                          % (payload["hooks"], payload["classes"]))
                    for c in payload.get("skipped", []):
                        print("    [-] class not found, skipped:", c)
                elif ev == "fatal":
                    print("[!]", payload.get("message"))
                    stop.set()
                else:
                    print("[js]", payload.get("message"))
                return
            if not isinstance(payload, dict):
                print("[js]", payload)
                return
            with lock:
                fh.write(json.dumps(payload, default=str) + "\n")
                fh.flush()
                count[0] += 1
            ts = datetime.datetime.fromtimestamp(payload["timestamp"] / 1000).strftime("%H:%M:%S.%f")[:-3]
            ret = ("EXC " + payload["exception"]) if payload.get("exception") else payload["returnValue"]
            print("[%s] %-18s %s.%s(%s) -> %s" % (
                ts, payload["category"], payload["class"], payload["method"],
                ", ".join(payload["args"]), ret))
        elif t == "error":
            print("[!] agent error:", message.get("description"))

    device = session = script = None
    pid = None
    try:
        device = frida.get_usb_device(timeout=10)
        print("[+] device:", device.name)
        if args.attach:
            running_pid = find_pid(device, args.package)
            if running_pid is None:
                sys.exit("[-] %s is not running. Open it first, or leave out --attach to let the script start it." % args.package)
            session = device.attach(running_pid)
        else:
            pid = device.spawn([args.package])
            session = device.attach(pid)
        script = session.create_script(build_agent(args.agent))
        script.on("message", on_message)
        script.load()
        script.exports_sync.init(config)   # hooks go in BEFORE the app runs
        if pid is not None:
            device.resume(pid)
        print("[+] monitoring for %d s - use the app now (Ctrl+C to stop early)" % args.duration)
        stop.wait(args.duration)
    except KeyboardInterrupt:
        print("\n[!] stopping")
    finally:
        for fn in (lambda: script and script.unload(),
                   lambda: session and session.detach()):
            try:
                fn()
            except Exception:
                pass
        fh.close()
        print("[+] %d calls recorded -> %s" % (count[0], os.path.abspath(args.out)))


if __name__ == "__main__":
    main()
