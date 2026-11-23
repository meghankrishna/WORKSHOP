#!/usr/bin/env python3
# emulator_control.py -- Task 3 (emulator environment control)


import os
import re
import sys
import time
import json
import argparse
import subprocess

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))


def _project_dir():
    # works for both layouts: Config/ next to this script (flat), or
    # Source/ + Config/ side by side (script lives in Source/)
    if os.path.isdir(os.path.join(SOURCE_DIR, "Config")):
        return SOURCE_DIR
    return os.path.dirname(SOURCE_DIR)


PROJECT_DIR = _project_dir()
CONFIG_DIR = os.path.join(PROJECT_DIR, "Config")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "Output")

# None = auto-detect the single running emulator (emulator-5554 for task1.sh).
# pass --device localhost:5555 for an ssh-tunnelled / adb-over-network device
# (note: `adb emu` console commands only work on emulator-XXXX serials).
DEFAULT_DEVICE = None
DEFAULT_CONFIG = os.path.join(CONFIG_DIR, "emulator_config.json")
DEFAULT_LOG = os.path.join(OUTPUT_DIR, "emulator_scenario_log.txt")
DEFAULT_WAIT = 20  # seconds to sit in each scenario before moving to the next one

DEBUG = False  # flip via --debug if you want to see every raw adb command + response


def run_cmd(args_list, label=""):
    # hands back the whole CompletedProcess so callers can look at stdout AND
    # stderr AND the return code. the first version of this only ever returned
    # stdout, which is exactly how we ended up not noticing adb was failing on
    # literally everything.
    if DEBUG:
        print(f"    $ {' '.join(args_list)}")
    try:
        res = subprocess.run(args_list, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        print(f"[-] Command timed out: {' '.join(args_list)}")
        return None
    except Exception as e:
        print(f"[-] Command flat out failed to run ({label}): {e}")
        return None

    if DEBUG and res.stdout.strip():
        print(f"      stdout: {res.stdout.strip()}")

    if res.returncode != 0 or res.stderr.strip():
        # this used to get silently swallowed - now we actually see it
        print(
            f"[-] adb complained on '{label}': {res.stderr.strip() or res.stdout.strip()}"
        )

    return res


def adb_shell(device, args):
    # normal shell commands on the device (dumpsys, am, pm, monkey...)
    return run_cmd(
        ["adb", "-s", device, "shell"] + args, label="shell " + " ".join(args)
    )


def adb_emu(device, args):
    # emulator console commands (geo, network) - these don't go through the
    # android shell at all, they talk to the emulator process itself
    return run_cmd(["adb", "-s", device, "emu"] + args, label="emu " + " ".join(args))


def list_ready_devices():
    devices = run_cmd(["adb", "devices"], label="adb devices")
    if devices is None:
        print("[-] Fatal: couldn't even run 'adb devices'. Is adb on your PATH?")
        sys.exit(1)
    ready = []
    for line in devices.stdout.strip().splitlines()[1:]:  # skip the header line
        parts = line.split()
        # state has to be "device", not "offline" or "unauthorized"
        if len(parts) >= 2 and parts[1] == "device":
            ready.append(parts[0])
    return ready, devices.stdout


def detect_device():
    # no --device given: use the one running emulator, so the default works
    # with task1.sh (emulator-5554) without editing this file
    ready, raw = list_ready_devices()
    emulators = [d for d in ready if d.startswith("emulator-")]
    candidates = emulators or ready
    if len(candidates) == 1:
        print(f"[*] Auto-detected device: {candidates[0]}")
        return candidates[0]
    if not candidates:
        print("[-] Fatal: no adb device is connected. Is the emulator running?")
    else:
        print(f"[-] Fatal: several devices connected ({', '.join(candidates)}); pick one with --device")
    print(raw)
    sys.exit(1)


def ensure_device_connected(device):
    # a local emulator shows up on its own, but a network device like
    # localhost:5555 has to be connected explicitly or every -s <device>
    # command fails with "device not found"
    if ":" in device:
        print(f"[*] Making sure adb is connected to {device} ...")
        run_cmd(["adb", "connect", device], label="adb connect")

    ready, raw = list_ready_devices()
    # exact match: "emulator-555" must not match "emulator-5554"
    if device not in ready:
        print(f"[-] Fatal: {device} is not showing up as a connected device.")
        print(raw)
        print(
            "    Check: is the emulator actually running? is the ssh tunnel still up?"
        )
        sys.exit(1)

    print(f"[+] {device} is connected.\n")


# ---- battery ----


def change_battery_console(device, level, charging):
    # emulator console (adb emu == telnet localhost:<console port>): this
    # changes the virtual battery hardware itself, so Android sees it the same
    # way it would see a real battery change
    print(f"[*] Setting battery to {level}% (charging={charging}) via emulator console")
    # drop any earlier `dumpsys battery set` overrides first -- while those are
    # active, the framework ignores what the (virtual) hardware reports
    adb_shell(device, ["dumpsys", "battery", "reset"])
    adb_emu(device, ["power", "ac", "on" if charging else "off"])
    adb_emu(device, ["power", "status", "charging" if charging else "discharging"])
    adb_emu(device, ["power", "capacity", str(level)])


def change_battery_dumpsys(device, level, charging):
    # fallback: override what the framework reports, no hardware change
    print(f"[*] Falling back to dumpsys battery override ({level}%, charging={charging})")
    if charging:
        # ac 1 = plugged into the charger, status 2 = BATTERY_STATUS_CHARGING
        adb_shell(device, ["dumpsys", "battery", "set", "ac", "1"])
        adb_shell(device, ["dumpsys", "battery", "set", "status", "2"])
    else:
        adb_shell(device, ["dumpsys", "battery", "unplug"])
    # set the level last, unplug can reset it otherwise
    adb_shell(device, ["dumpsys", "battery", "set", "level", str(level)])


def read_battery(device):
    res = adb_shell(device, ["dumpsys", "battery"])
    if res is None:
        return None, None, ""
    out = res.stdout
    # match the whole line: a plain substring test would accept "level: 50"
    # when we asked for 5
    m = re.search(r"^\s*level:\s*(\d+)\s*$", out, re.MULTILINE)
    ac = re.search(r"^\s*AC powered:\s*(true|false)\s*$", out, re.MULTILINE)
    level = int(m.group(1)) if m else None
    ac_on = (ac.group(1) == "true") if ac else None
    return level, ac_on, out


def check_battery(device, expected_level, expected_charging, attempts=5):
    # read it back instead of trusting that the set worked. the console change
    # travels through the battery HAL, so give it a few seconds to show up
    out = ""
    for _ in range(attempts):
        level, ac_on, out = read_battery(device)
        if level == expected_level and (ac_on is None or ac_on == bool(expected_charging)):
            print(f"[+] Battery change verified (level={level}, ac={ac_on}).")
            return True, out
        time.sleep(1)

    print("[-] Battery didn't change the way we expected, raw dump below:")
    print(out)
    return False, out


def change_battery(device, level, charging):
    # returns (verified, method) so the log records HOW the change was made
    change_battery_console(device, level, charging)
    ok, _ = check_battery(device, level, charging)
    if ok:
        return True, "emulator console (power)"
    change_battery_dumpsys(device, level, charging)
    ok, _ = check_battery(device, level, charging)
    return ok, "dumpsys battery override"


# ---- gps ----


def update_gps(device, lon, lat):
    # note the order - geo fix takes longitude FIRST, then latitude. got this
    # backwards at first and ended up somewhere in the ocean.
    print(f"[*] Setting GPS to lon={lon}, lat={lat}")
    res = adb_emu(device, ["geo", "fix", str(lon), str(lat)])
    if res and "OK" in res.stdout:
        print("[+] Emulator console confirmed the GPS fix (said OK).")
        return True, res.stdout.strip()

    out = res.stdout.strip() if res else "no response"
    print(f"[-] Emulator console didn't confirm the geo fix, got: {out}")
    return False, out


# ---- network ----


def throttle_network(device, speed):
    print(f"[*] Setting network speed to {speed}")
    res = adb_emu(device, ["network", "speed", str(speed)])
    ok = bool(res and "OK" in res.stdout)
    if ok:
        print("[+] Network speed change confirmed.")
    else:
        print(
            f"[-] Network speed change wasn't confirmed, got: {res.stdout.strip() if res else 'no response'}"
        )
    return ok, (res.stdout.strip() if res else "")


def restore_defaults(device):
    print("[*] Putting the emulator back to normal so it isn't stuck in a weird state")
    adb_shell(device, ["dumpsys", "battery", "reset"])
    adb_emu(device, ["power", "ac", "on"])
    adb_emu(device, ["power", "status", "charging"])
    adb_emu(device, ["power", "capacity", "100"])
    adb_emu(device, ["network", "speed", "full"])
    # note: there's no clean "un-fix" for GPS via the console -- the last
    # geo fix just sticks around until you set it again or restart the AVD


# ---- launching the app and checking it really came up ----


def is_package_installed(device, pkg):
    res = adb_shell(device, ["pm", "list", "packages", pkg])
    if res is None:
        return False
    return f"package:{pkg}" in res.stdout


def get_foreground_activity(device):
    res = adb_shell(device, ["dumpsys", "activity", "activities"])
    if res is None:
        return "unknown"
    for line in res.stdout.splitlines():
        # the field name changed between android versions, so check both
        if "mResumedActivity" in line or "mFocusedActivity" in line:
            return line.strip()
    return "unknown (couldn't find it in dumpsys output)"


def open_app(device, pkg):
    print(f"[*] Trying to launch {pkg}")

    if not is_package_installed(device, pkg):
        print(f"[-] {pkg} doesn't seem to be installed on the device at all!")
        return False, "package not installed"

    # cold start every scenario: if the app is still running from the previous
    # scenario, `am start` just brings it to the front and it never re-reads
    # the new conditions at startup
    adb_shell(device, ["am", "force-stop", pkg])

    # ask the package manager which activity is the launcher one, so we don't
    # have to hardcode ".MainActivity" and hope
    resolve = adb_shell(device, ["cmd", "package", "resolve-activity", "--brief", pkg])
    activity = None
    if resolve and resolve.stdout.strip():
        candidates = [
            l.strip() for l in resolve.stdout.strip().splitlines() if "/" in l
        ]
        if candidates:
            activity = candidates[-1]  # last "/"-containing line is the component name

    launched_ok = False
    method_used = ""

    if activity:
        print(f"[*] Resolved launcher activity: {activity} -- using am start")
        res = adb_shell(device, ["am", "start", "-n", activity])
        method_used = f"am start -n {activity}"
        # am start happily returns 0 and prints "Error:" in the output, so
        # check the text too
        if res and "Error" not in res.stdout and "Exception" not in res.stdout:
            launched_ok = True
    else:
        print("[!] Couldn't resolve a launcher activity, falling back to monkey")

    if not launched_ok:
        res = adb_shell(
            device, ["monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"]
        )
        method_used = "monkey -c LAUNCHER"
        if (
            res
            and "No activities found" not in res.stdout
            and "aborted" not in res.stdout
        ):
            launched_ok = True

    time.sleep(2)  # give the app a second to actually come up before we check
    foreground = get_foreground_activity(device)
    actually_visible = pkg in foreground

    if launched_ok and actually_visible:
        print(f"[+] {pkg} launched and is in the foreground.")
    elif launched_ok and not actually_visible:
        # happens when the app crashes on startup - the launch "worked" but
        # nothing is on screen
        print(
            f"[!] Launch command didn't error, but {pkg} isn't in the foreground. Current: {foreground}"
        )
    else:
        print(f"[-] Failed to launch {pkg}.")

    return (
        launched_ok and actually_visible
    ), f"method={method_used}, foreground={foreground}"


# ---- logging ----


def save_log(log_path, json_log_path, scenario_name, app, details):
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    # human-readable block, easy to skim while you're watching the emulator
    with open(log_path, "a") as f:
        f.write("=" * 70 + "\n")
        f.write(f"Scenario   : {scenario_name}\n")
        f.write(f"App        : {app}\n")
        f.write(f"Time       : {now}\n")
        f.write("-" * 70 + "\n")

        if details["battery"]:
            b = details["battery"]
            f.write(
                f"Battery    : requested level={b['requested_level']} charging={b['requested_charging']}\n"
            )
            f.write(
                f"             verified={'PASS' if b['verified'] else 'FAIL'} method={b['method']}\n"
            )
        else:
            f.write("Battery    : not changed in this scenario\n")

        if details["gps"]:
            g = details["gps"]
            f.write(
                f"GPS        : requested lon={g['lon']} lat={g['lat']} confirmed={'yes' if g['ok'] else 'no'}\n"
            )
        else:
            f.write("GPS        : not changed in this scenario\n")

        if details["network"]:
            n = details["network"]
            f.write(
                f"Network    : requested speed={n['speed']} confirmed={'yes' if n['ok'] else 'no'}\n"
            )
        else:
            f.write("Network    : not changed in this scenario\n")

        f.write(
            f"App launch : {'SUCCESS' if details['app_launched'] else 'FAILED'} ({details['app_launch_info']})\n"
        )
        f.write("=" * 70 + "\n\n")

    # also keep a JSON-lines version -- basically free to add now and will
    # save a lot of pain when Task 6 needs to parse everything automatically
    # into the final report
    event = {"timestamp": now, "scenario": scenario_name, "app": app, **details}
    with open(json_log_path, "a") as f:
        f.write(json.dumps(event) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Task 3 - run an app under different emulator conditions"
    )
    parser.add_argument(
        "package", help="package name of the target app, e.g. jakhar.aseem.diva"
    )
    parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE,
        help="adb device serial (default: auto-detect the running emulator)",
    )
    parser.add_argument(
        "--config", default=DEFAULT_CONFIG, help="path to the scenarios config json"
    )
    parser.add_argument(
        "--wait", type=int, default=DEFAULT_WAIT, help="seconds to sit in each scenario"
    )
    parser.add_argument("--log", default=DEFAULT_LOG, help="text log path")
    parser.add_argument(
        "--debug", action="store_true", help="print raw adb output for every command"
    )
    args = parser.parse_args()

    global DEBUG
    DEBUG = args.debug

    if not os.path.exists(args.config):
        print(f"Fatal: need '{args.config}' to know which scenarios to run")
        sys.exit(1)

    with open(args.config) as f:
        data = json.load(f)
    scenarios = data.get("scenarios", {})

    if not scenarios:
        print("Fatal: no scenarios found in the config file")
        sys.exit(1)

    # same name as the text log but .jsonl
    json_log_path = os.path.splitext(args.log)[0] + ".jsonl"

    os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)

    print(f"Loaded {len(scenarios)} scenario(s) for {args.package}\n")

    if args.device is None:
        args.device = detect_device()
    ensure_device_connected(args.device)

    # always put the emulator back, even on Ctrl+C or a crash mid-scenario
    try:
        run_scenarios(args, scenarios, json_log_path)
    except KeyboardInterrupt:
        print("\n[!] Interrupted.")
    finally:
        print("\n[*] Resetting emulator back to normal")
        restore_defaults(args.device)
    print(f"[+] All set. Check {args.log} and {json_log_path} for the detailed logs.")


def run_scenarios(args, scenarios, json_log_path):
    for name, cfg in scenarios.items():
        print(f"\n--- Running scenario: {name} ---")
        details = {
            "battery": None,
            "gps": None,
            "network": None,
            "app_launched": False,
            "app_launch_info": "",
        }

        # each of these is optional - a scenario only changes what it lists,
        # and "is not None" matters here because battery_level can be 0
        if cfg.get("battery_level") is not None:
            charging = bool(cfg.get("is_charging"))
            verified, method = change_battery(
                args.device, cfg["battery_level"], charging
            )
            details["battery"] = {
                "requested_level": cfg["battery_level"],
                "requested_charging": charging,
                "verified": verified,
                "method": method,
            }

        if cfg.get("location") is not None:
            lon, lat = cfg["location"]
            ok, _ = update_gps(args.device, lon, lat)
            details["gps"] = {"lon": lon, "lat": lat, "ok": ok}

        if cfg.get("network_speed") is not None:
            ok, _ = throttle_network(args.device, cfg["network_speed"])
            details["network"] = {"speed": cfg["network_speed"], "ok": ok}

        # launch after the conditions are set, so the app sees them at startup
        launched, info = open_app(args.device, args.package)
        details["app_launched"] = launched
        details["app_launch_info"] = info

        save_log(args.log, json_log_path, name, args.package, details)

        print(
            f"[*] {name} is active, sitting here for {args.wait}s so you can poke around / watch it in the emulator"
        )
        time.sleep(args.wait)

    print("\n[*] Done with all scenarios")


if __name__ == "__main__":
    main()
