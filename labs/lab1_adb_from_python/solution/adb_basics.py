#!/usr/bin/env python3
"""Lab 1 solution: talk to the emulator from Python."""
import subprocess


def run_adb(*args):
    """Run `adb <args>` and return everything it printed (as text)."""
    result = subprocess.run(["adb", *args], capture_output=True, text=True)
    if result.returncode != 0 and result.stderr.strip():
        print("[adb error]", result.stderr.strip())  # show errors, don't hide them
    return result.stdout.strip()


def list_emulators():
    """Return the names of emulators that are ready, e.g. ["emulator-5554"]."""
    text = run_adb("devices")
    ready = []
    for line in text.splitlines()[1:]:          # skip the "List of devices..." line
        words = line.split()
        if len(words) >= 2 and words[1] == "device" and words[0].startswith("emulator-"):
            ready.append(words[0])
    return ready


def get_prop(serial, name):
    """Read one phone setting, e.g. get_prop("emulator-5554", "ro.product.model")."""
    return run_adb("-s", serial, "shell", "getprop", name)


def describe_device(serial):
    """Return {"model": ..., "android": ..., "booted": True/False}."""
    return {
        "model": get_prop(serial, "ro.product.model"),
        "android": get_prop(serial, "ro.build.version.release"),
        "booted": get_prop(serial, "sys.boot_completed") == "1",
    }


if __name__ == "__main__":
    emulators = list_emulators()
    print("Emulators found:", emulators)
    if emulators:
        print("Device info:", describe_device(emulators[0]))
    else:
        print("No emulator is running. Start one, then try again.")
