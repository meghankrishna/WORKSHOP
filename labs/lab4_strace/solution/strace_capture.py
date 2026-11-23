#!/usr/bin/env python3
"""Lab 4 solution, part 1: run strace on an app and bring the raw log back.

    python3 strace_capture.py com.bootcamp.demoapp --duration 30 --out raw_strace.log

While it runs, USE THE APP: strace only records what the app does.
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def adb(serial, *args, timeout=60):
    """Run `adb -s <serial> <args>`; return (returncode, stdout, stderr)."""
    r = subprocess.run(["adb", "-s", serial, *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def find_emulator():
    out = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout
    ready = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device" and parts[0].startswith("emulator-"):
            ready.append(parts[0])
    if len(ready) != 1:
        sys.exit("[-] Need exactly one running emulator, found: %s" % (ready or "none"))
    return ready[0]


def find_pid(serial, package):
    """Process id of the running app ('' if it is not running)."""
    _, out, _ = adb(serial, "shell", "pidof", package)
    words = out.split()
    return words[0] if words else ""


def build_strace_command(pid, config, remote_file):
    """Build the strace command line from the config file."""
    st = config["strace"]
    wanted = []
    for syscalls in config["categories"].values():
        wanted.extend(syscalls)

    cmd = ["strace"]
    if st.get("follow_children_and_threads", True):
        cmd.append("-f")                       # follow threads and child programs
    if st.get("timestamps", True):
        cmd.append("-tt")                      # time on every line
    cmd += ["-s", str(st.get("string_limit", 128))]
    cmd += ["-e", "trace=" + ",".join(wanted)] # only the calls we care about
    cmd += ["-o", remote_file, "-p", str(pid)]
    return " ".join(cmd)


def run_strace(serial, strace_cmd, seconds):
    """Run strace as root on the phone for `seconds`, then let it finish cleanly."""
    # `timeout -s INT` stops strace with Ctrl+C, so it writes out the whole file
    on_device = "su -c 'timeout -s INT %d %s'" % (seconds, strace_cmd)
    return adb(serial, "shell", on_device, timeout=seconds + 30)


def pull_text(serial, remote_file):
    r = subprocess.run(["adb", "-s", serial, "exec-out", "su -c 'cat %s'" % remote_file],
                       capture_output=True, text=True, timeout=60)
    return r.stdout


def main():
    p = argparse.ArgumentParser(description="Lab 4: capture system calls of an app with strace")
    p.add_argument("package")
    p.add_argument("--config", default=os.path.join(HERE, "strace_config.json"))
    p.add_argument("--duration", type=int, default=None, help="seconds to trace (default: from config)")
    p.add_argument("--out", default="raw_strace.log")
    p.add_argument("--device", default=None)
    args = p.parse_args()

    with open(args.config) as f:
        config = json.load(f)
    seconds = args.duration or config["capture"]["duration_seconds"]

    serial = args.device or find_emulator()
    print("[+] Using", serial)

    pid = find_pid(serial, args.package)
    if not pid:
        sys.exit("[-] %s is not running. Open it on the emulator first." % args.package)
    print("[+] %s has process id %s" % (args.package, pid))

    remote_file = "%s/lab4_strace.log" % config["capture"]["remote_dir"]
    adb(serial, "shell", "su -c 'rm -f %s'" % remote_file)

    cmd = build_strace_command(pid, config, remote_file)
    print("[+] On the phone: %s" % cmd)
    print("[+] Tracing for %d s. USE THE APP NOW (tap its buttons)." % seconds)
    _, out, err = run_strace(serial, cmd, seconds)
    if "Operation not permitted" in (out + err) or "No such process" in (out + err):
        print("[!] strace could not attach:", (out + err).splitlines()[0])

    text = pull_text(serial, remote_file)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)
    adb(serial, "shell", "su -c 'rm -f %s'" % remote_file)

    lines = len(text.splitlines())
    print("[+] %d lines of raw strace output -> %s" % (lines, os.path.abspath(args.out)))
    if lines == 0:
        print("[!] Nothing was recorded. Did you use the app while it was tracing?")


if __name__ == "__main__":
    main()
