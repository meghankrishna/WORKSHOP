#!/usr/bin/env python3
"""Lab 2 starter: scenario-driven emulator control.

Fill in every TODO. Run:
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
    """Run a command, return (returncode, stdout, stderr). Provided for you."""
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


class Emulator:
    def __init__(self, serial=None):
        self.serial = serial or self.detect()
        print(f"[+] Using {self.serial}")

    @staticmethod
    def detect():
        # TODO 1: run `adb devices`, collect serials that start with "emulator-"
        # and whose state is "device". Exit with a clear message unless there
        # is exactly one.
        raise NotImplementedError

    def adb(self, *args):
        return run(["adb", "-s", self.serial, *args])

    def shell(self, *args):
        # TODO 2: run `adb -s <serial> shell <args>` and return stdout only.
        raise NotImplementedError

    def emu(self, *args):
        # TODO 3: run `adb -s <serial> emu <args>` (emulator console).
        # Return (ok, text). The console ends successful replies with "OK";
        # failures contain "KO".
        raise NotImplementedError

    # ---- battery ----
    def set_battery(self, level, charging):
        # TODO 4: 1) `dumpsys battery reset` (clear old overrides)
        #         2) console: power ac on/off
        #         3) console: power status charging/discharging
        #         4) console: power capacity <level>
        raise NotImplementedError

    def set_battery_override(self, level, charging):
        """PROVIDED FOR YOU. Fallback: tell Android directly what the battery is.
        Use it when the console change does not show up in `dumpsys battery`."""
        if charging:
            self.shell("dumpsys", "battery", "set", "ac", "1")
            self.shell("dumpsys", "battery", "set", "status", "2")
        else:
            self.shell("dumpsys", "battery", "unplug")
        self.shell("dumpsys", "battery", "set", "level", str(level))

    def read_battery(self):
        # TODO 5: parse `dumpsys battery`. Return (level:int|None, ac:bool|None).
        # Match WHOLE lines with a regex: r"^\s*level:\s*(\d+)\s*$" (re.M).
        # A substring test accepts "level: 50" when you asked for 5.
        raise NotImplementedError

    def verify_battery(self, level, charging, tries=5):
        # TODO 6: poll read_battery() up to `tries` times, 1 s apart.
        # Return (confirmed:bool, observed:dict).
        raise NotImplementedError

    # ---- location ----
    def set_location(self, lat, lon):
        # TODO 7: console `geo fix <lon> <lat>` -- LONGITUDE FIRST.
        raise NotImplementedError

    def verify_location(self, lat, lon):
        # TODO 8: search `dumpsys location` for the coordinates (e.g. f"{lat:.4f}").
        # Return "confirmed" if found, otherwise "console-only".
        raise NotImplementedError

    # ---- network ----
    def set_network(self, speed):
        # TODO 9: console `network speed <speed>`.
        raise NotImplementedError

    # ---- app ----
    def launch(self, package):
        # TODO 10: force-stop the package, `logcat -c`, launch it with
        #   monkey -p <pkg> -c android.intent.category.LAUNCHER 1
        # wait ~2 s, then check the foreground activity from
        # `dumpsys activity activities` (look for mResumedActivity containing the package).
        # Return {"launched": bool, "foreground": bool}.
        raise NotImplementedError

    def capture_logcat(self, package, path):
        # TODO 11: get the app's pid (`pidof <pkg>`), then write
        # `logcat -d --pid=<pid>` output to `path`. If the app is not running
        # (it crashed), write the unfiltered last 200 lines instead and say so.
        # Return the number of lines written.
        raise NotImplementedError

    def restore(self):
        # TODO 12: dumpsys battery reset; power ac on; power status charging;
        # power capacity 100; network speed full.
        raise NotImplementedError


def run_scenarios(emu, cfg, args):
    os.makedirs(os.path.join(args.output, "logcat"), exist_ok=True)
    results_path = os.path.join(args.output, "results.jsonl")
    with open(results_path, "w") as out:
        for name, sc in cfg["scenarios"].items():
            print(f"--- scenario: {name} ---")
            rec = {"scenario": name, "time": time.strftime("%Y-%m-%d %H:%M:%S")}

            # TODO 13: for each of battery / location / network that is present
            # in `sc` (use `"battery" in sc`, because level 0 is valid):
            #   apply it, verify it, and store the outcome in `rec`.
            #   For battery: if verify_battery() is False after the console
            #   change, call emu.set_battery_override(...) and verify again,
            #   and record which method worked (some emulators ignore the
            #   console battery change).

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
    # TODO 14: wrap run_scenarios in try/finally so emu.restore() ALWAYS runs,
    # including on Ctrl+C.
    results = run_scenarios(emu, cfg, args)
    print(f"[+] Results: {results}")


if __name__ == "__main__":
    main()
