#!/usr/bin/env python3
"""Lab 1: talk to the emulator from Python.

Fill in each TODO, then run:  python3 adb_basics.py
"""
import subprocess


def run_adb(*args):
    """Run `adb <args>` and return everything it printed (as text).

    Example: run_adb("devices")  ->  "List of devices attached\nemulator-5554\tdevice"
    """
    # TODO 1: use subprocess.run(["adb", *args], capture_output=True, text=True)
    #         and return its .stdout with spaces/newlines trimmed off (.strip()).
    raise NotImplementedError


def list_emulators():
    """Return the names of emulators that are ready, e.g. ["emulator-5554"]."""
    text = run_adb("devices")
    ready = []
    # TODO 2: loop over text.splitlines()[1:]   (skip the first "List of..." line)
    #         split each line into words with line.split()
    #         if there are 2+ words, the 2nd is "device" and the 1st starts with
    #         "emulator-", add the 1st word to `ready`.
    return ready


def get_prop(serial, name):
    """Read one phone setting, e.g. get_prop("emulator-5554", "ro.product.model")."""
    # TODO 3: return run_adb("-s", serial, "shell", "getprop", name)
    raise NotImplementedError


def describe_device(serial):
    """Return {"model": ..., "android": ..., "booted": True/False}."""
    # TODO 4: use get_prop three times:
    #   model   -> "ro.product.model"
    #   android -> "ro.build.version.release"
    #   booted  -> get_prop(serial, "sys.boot_completed") == "1"
    raise NotImplementedError


if __name__ == "__main__":
    emulators = list_emulators()
    print("Emulators found:", emulators)
    if emulators:
        print("Device info:", describe_device(emulators[0]))
    else:
        print("No emulator is running. Start one, then try again.")
