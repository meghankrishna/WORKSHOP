#!/usr/bin/env python3
"""Lab 2 solution: scenario-driven emulator control.

Run:
    python3 emulator_control.py --config scenarios.json --package <pkg> --wait 5
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd, timeout=20):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


class Emulator:
    def __init__(self, serial=None):
        self.serial = serial or self.detect()
        print(f"[+] Using {self.serial}")

    @staticmethod
    def detect():
        _, out, _ = run(["adb", "devices"])
        emus = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device" and parts[0].startswith("emulator-"):
                emus.append(parts[0])
        if len(emus) != 1:
            sys.exit(f"[-] Need exactly one running emulator, found: {emus or 'none'}")
        return emus[0]

    def adb(self, *args):
        return run(["adb", "-s", self.serial, *args])

    def shell(self, *args):
        return self.adb("shell", *args)[1]

    def emu(self, *args):
        _, out, err = self.adb("emu", *args)
        text = out or err
        return ("OK" in text and "KO" not in text), text

    # ---- battery ----
    def set_battery(self, level, charging):
        self.shell("dumpsys", "battery", "reset")  # drop old overrides first
        self.emu("power", "ac", "on" if charging else "off")
        self.emu("power", "status", "charging" if charging else "discharging")
        ok, _ = self.emu("power", "capacity", str(level))
        return ok

    def set_battery_override(self, level, charging):
        """Fallback: tell Android directly what the battery is (no hardware change).
        Used when the console change does not show up in `dumpsys battery`."""
        if charging:
            self.shell("dumpsys", "battery", "set", "ac", "1")
            self.shell("dumpsys", "battery", "set", "status", "2")   # 2 = charging
        else:
            self.shell("dumpsys", "battery", "unplug")
        self.shell("dumpsys", "battery", "set", "level", str(level))  # level last

    def read_battery(self):
        out = self.shell("dumpsys", "battery")
        # whole-line match: "level: 5" must not match "level: 50"
        m = re.search(r"^\s*level:\s*(\d+)\s*$", out, re.M)
        ac = re.search(r"^\s*AC powered:\s*(true|false)\s*$", out, re.M)
        return (int(m.group(1)) if m else None,
                (ac.group(1) == "true") if ac else None)

    def verify_battery(self, level, charging, tries=5):
        observed = {}
        for _ in range(tries):
            lvl, ac = self.read_battery()
            observed = {"level": lvl, "ac": ac}
            if lvl == level and (ac is None or ac == charging):
                return True, observed
            time.sleep(1)
        return False, observed

    # ---- location ----
    def set_location(self, lat, lon):
        ok, _ = self.emu("geo", "fix", str(lon), str(lat))  # longitude first
        return ok

    def verify_location(self, lat, lon):
        time.sleep(1)
        out = self.shell("dumpsys", "location")
        return "confirmed" if f"{lat:.4f}" in out else "console-only"

    # ---- network ----
    def set_network(self, speed):
        ok, _ = self.emu("network", "speed", speed)
        _, status = self.emu("network", "status")
        return ok, status

    # ---- app ----
    def launch(self, package):
        self.shell("am", "force-stop", package)  # cold start every scenario
        self.adb("logcat", "-c")
        out = self.shell("monkey", "-p", package, "-c",
                         "android.intent.category.LAUNCHER", "1")
        launched = "No activities found" not in out and "aborted" not in out
        time.sleep(2)
        dump = self.shell("dumpsys", "activity", "activities")
        foreground = any(package in l for l in dump.splitlines()
                         if "mResumedActivity" in l or "mFocusedActivity" in l)
        print(f"[{'+' if launched and foreground else '!'}] launched {package} "
              f"(foreground: {'yes' if foreground else 'no'})")
        return {"launched": launched, "foreground": foreground}

    def capture_logcat(self, package, path):
        pid = self.shell("pidof", package).split()
        if pid:
            _, text, _ = self.adb("logcat", "-d", f"--pid={pid[0]}")
            header = ""
        else:
            _, text, _ = self.adb("logcat", "-d", "-t", "200")
            header = "# app not running (crashed?) - unfiltered last 200 lines\n"
        with open(path, "w") as f:
            f.write(header + text + "\n")
        return len(text.splitlines())

    def restore(self):
        print("[*] Restoring defaults")
        self.shell("dumpsys", "battery", "reset")
        self.emu("power", "ac", "on")
        self.emu("power", "status", "charging")
        self.emu("power", "capacity", "100")
        self.emu("network", "speed", "full")


def run_scenarios(emu, cfg, args):
    os.makedirs(os.path.join(args.output, "logcat"), exist_ok=True)
    results_path = os.path.join(args.output, "results.jsonl")
    with open(results_path, "w") as out:
        for name, sc in cfg["scenarios"].items():
            print(f"--- scenario: {name} ---")
            rec = {"scenario": name, "time": time.strftime("%Y-%m-%d %H:%M:%S")}

            if "battery" in sc:
                b = sc["battery"]
                level, charging = b["level"], bool(b.get("charging", False))
                method = "emulator console"
                emu.set_battery(level, charging)
                ok, observed = emu.verify_battery(level, charging)
                if not ok:
                    # On some emulators Android does not pick up the console
                    # change. Fall back to the dumpsys override and say so.
                    print("[!] console change not seen by Android; using dumpsys override")
                    method = "dumpsys override"
                    emu.set_battery_override(level, charging)
                    ok, observed = emu.verify_battery(level, charging)
                rec["battery"] = {"requested": {"level": level, "charging": charging},
                                  "observed": observed, "confirmed": ok,
                                  "method": method}
                print(f"[{'+' if ok else '-'}] battery ({method}): requested {level}% "
                      f"charging={charging}, read back {observed} -> "
                      f"{'confirmed' if ok else 'NOT confirmed'}")

            if "location" in sc:
                lat, lon = sc["location"]["lat"], sc["location"]["lon"]
                console_ok = emu.set_location(lat, lon)
                status = emu.verify_location(lat, lon) if console_ok else "failed"
                rec["location"] = {"requested": {"lat": lat, "lon": lon},
                                   "status": status}
                print(f"[*] location: lat={lat} lon={lon} -> {status}")

            if "network" in sc:
                speed = sc["network"]
                console_ok, status_text = emu.set_network(speed)
                rec["network"] = {"requested": speed, "console_ok": console_ok,
                                  "status": status_text}
                print(f"[{'+' if console_ok else '-'}] network speed {speed}: "
                      f"{'console OK' if console_ok else 'console error'}")

            rec["app"] = emu.launch(args.package)
            time.sleep(args.wait)
            log_path = os.path.join(args.output, "logcat", f"{name}.log")
            rec["logcat_lines"] = emu.capture_logcat(args.package, log_path)

            out.write(json.dumps(rec) + "\n")
            out.flush()
    return results_path


def main():
    p = argparse.ArgumentParser(description="Lab 2: emulator scenario runner")
    p.add_argument("--config", default=os.path.join(HERE, "scenarios.json"))
    p.add_argument("--package", required=True)
    p.add_argument("--device", default=None, help="emulator serial (default: auto-detect)")
    p.add_argument("--wait", type=int, default=10, help="seconds to observe each scenario")
    p.add_argument("--output", default=os.path.join(HERE, "output"))
    args = p.parse_args()

    with open(args.config) as f:
        cfg = json.load(f)

    emu = Emulator(args.device)
    try:
        results = run_scenarios(emu, cfg, args)
        print(f"[+] Results: {results}")
    except KeyboardInterrupt:
        print("\n[!] Interrupted")
    finally:
        emu.restore()


if __name__ == "__main__":
    main()
