#!/usr/bin/env python3
"""Lab 4, part 1: run strace on an app and bring the raw log back to your laptop.

Fill in each TODO, then run (with the Bootcamp Demo app open on the emulator):

    python3 strace_capture.py com.bootcamp.demoapp --duration 30 --out raw_strace.log

While it runs, USE THE APP: strace only records what the app does.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def adb(serial, *args, timeout=60):
    """PROVIDED. Run `adb -s <serial> <args>`; return (returncode, stdout, stderr)."""
    r = subprocess.run(["adb", "-s", serial, *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def find_emulator():
    """PROVIDED (same idea as Lab 1). Return the one running emulator's name."""
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
    """Process id of the running app, or "" if it is not running."""
    # TODO 1: run `adb -s <serial> shell pidof <package>` using the adb() helper above.
    #         adb() returns (returncode, stdout, stderr). pidof prints the number,
    #         e.g. "10350". Return it as text, or "" if nothing came back.
    raise NotImplementedError


def build_strace_command(pid, config, remote_file):
    """Build the strace command (as one string) from the config file."""
    st = config["strace"]

    # TODO 2a: collect every syscall name from config["categories"] into one list.
    #          categories looks like {"filesystem": ["openat", ...], "network": [...]}
    wanted = []

    # TODO 2b: build the command as a list of words, then join it with spaces:
    #   strace  -f  -tt  -s <string_limit>  -e trace=<names joined by commas>  -o <remote_file>  -p <pid>
    #   -f only if st["follow_children_and_threads"] is true; -tt only if st["timestamps"] is true.
    #   Example result:
    #   strace -f -tt -s 128 -e trace=openat,connect,execve -o /data/local/tmp/x.log -p 10350
    raise NotImplementedError


def run_strace(serial, strace_cmd, seconds):
    """Run strace as root on the phone for `seconds`, then let it finish cleanly."""
    # TODO 3: run this on the phone with adb(serial, "shell", <text>, timeout=seconds + 30):
    #           su -c 'timeout -s INT <seconds> <strace_cmd>'
    #         `timeout -s INT` stops strace with Ctrl+C so it writes out the whole file.
    #         Note the single quotes around the command after `su -c`.
    raise NotImplementedError


def pull_text(serial, remote_file):
    """PROVIDED. Read a text file from the phone (as root) and return its contents."""
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
    run_strace(serial, cmd, seconds)

    # TODO 4: pull the log back and save it.
    #   text = pull_text(serial, remote_file)
    #   write `text` to args.out   (make sure the folder exists: os.makedirs(..., exist_ok=True))
    #   delete the file on the phone:  adb(serial, "shell", "su -c 'rm -f %s'" % remote_file)
    #   print how many lines were saved; warn if there were none.
    raise NotImplementedError


if __name__ == "__main__":
    main()
