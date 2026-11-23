# Lab 2: Control the emulator with scenarios

**Time:** 90 minutes  **Difficulty:** ★★☆☆☆
**Prepares you for:** Assignment **Task 2** (Emulator Environment Control)
**Do first:** Lab 1 and Demo 2 (watch the instructor change the battery and location).

## What you will learn

- Change the emulator's battery, GPS location and network speed **from code**.
- **Verify** that a change really happened (do not just trust "OK").
- Start an app, watch what it does, and **always** put the emulator back to normal.

Unfamiliar word? See the [Glossary](../GLOSSARY.md).

## The big idea: scenarios

A *scenario* is a named situation, written in a config file so you never edit code to add one:

```json
"low_battery": { "battery": { "level": 5, "charging": false } }
```

Your program reads the file and, for each scenario, does this loop:

```
 set conditions → verify them → restart the app → wait → save what happened
                                                          │
                                  (when everything is finished) → reset the emulator
```

## The commands you will use

All of these go to the emulator **console** through `adb emu`. You saw them in Demo 2.

| Condition | Command | Careful! |
|-----------|---------|----------|
| Battery level | `adb emu power capacity 5` | 0 to 100 |
| Charger on/off | `adb emu power ac off` | |
| Charging state | `adb emu power status discharging` | `charging` or `discharging` |
| GPS | `adb emu geo fix 78.4867 17.385` | **longitude FIRST**, then latitude |
| Network speed | `adb emu network speed edge` | `full`, `edge`, `gprs`, `umts`, `hsdpa` |

To **verify** the battery, ask the phone: `adb shell dumpsys battery`.

## Your task

Open `starter/emulator_control.py` and `starter/scenarios.json`. The file already contains the program's skeleton (reading config, looping over scenarios, writing results). You fill in the numbered `TODO`s. We do it in four parts, **testing after each part** so mistakes are easy to find.

> Run all tests from inside the `starter/` folder.

---

### Part 1: Find the emulator and send commands (TODO 1, 2, 3)

This is Lab 1 again, now inside a class.

- `detect()`: use `adb devices` and keep exactly one `emulator-…` that is `device`.
- `shell(...)`: run `adb -s <serial> shell …`; return the printed text.
- `emu(...)`: run `adb -s <serial> emu …`; return `(ok, text)` where `ok` is `True` when the text contains `OK` and not `KO`.

**Checkpoint 1**
```bash
python3 -c "from emulator_control import Emulator; e=Emulator(); print(e.shell('getprop','ro.product.model')); print(e.emu('power','capacity','80'))"
```
Expected: your emulator name, then `(True, 'OK')`.

---

### Part 2: Battery (TODO 4, 5, 6)

- `set_battery(level, charging)`: reset old overrides, then three console commands (AC, status, capacity).
- `read_battery()`: read `dumpsys battery` and pull out `level` and `AC powered`.
- `verify_battery()`: read it back (try up to 5 times, 1 second apart) and compare.

> **Hint for `read_battery`**: use a regular expression that matches the **whole line**:
> ```python
> m = re.search(r"^\s*level:\s*(\d+)\s*$", out, re.M)
> level = int(m.group(1)) if m else None
> ```
> Why not `"level: 5" in out`? Because it would also match `level: 50`. (Demo 2 showed this.)

**Checkpoint 2**
```bash
python3 -c "
from emulator_control import Emulator
e=Emulator(); e.set_battery(5, False); print(e.verify_battery(5, False))"
```
Expected: `(True, {'level': 5, 'ac': False})`. Look at the emulator screen: battery 5%.
Try `verify_battery(6, False)`; it must return `False`. A check that cannot fail is useless.

> **If Checkpoint 2 says `False` even though the emulator screen shows the new battery:** on some emulators the console changes the *hardware* but Android does not notice. That is a real-world lesson, not a bug in your code. The starter already contains `set_battery_override(...)`, which tells Android directly (`adb shell dumpsys battery set ...`). In TODO 13 you will try the console first and, if the verify fails, call the override and record which method worked.

---

### Part 3: Location and network (TODO 7, 8, 9)

- `set_location(lat, lon)`: remember **longitude first** when you build the command.
- `verify_location(lat, lon)`: look for the coordinates in `dumpsys location`. Return `"confirmed"` if found, else `"console-only"` (the console said OK, but the phone did not show it yet).
- `set_network(speed)`: console command; also ask `network status` and return its text.

**Checkpoint 3**
```bash
python3 -c "
from emulator_control import Emulator
e=Emulator(); print(e.set_location(17.385, 78.4867)); print(e.verify_location(17.385, 78.4867)); print(e.set_network('edge')[0])"
```
Expected: `True`, `confirmed` (or `console-only`), `True`.

> Talking point for your report: *why is location verification weaker than battery verification?*

---

### Part 4: Launch the app, record, restore, run everything (TODO 10 to 14)

- `launch(package)`: **force-stop** the app first (otherwise it keeps running and never sees the new conditions), clear logcat, start it, check it is in the foreground.
- `capture_logcat(...)`: save what the app printed (`logcat`) into a file.
- `restore()`: put battery, charger and network back to normal.
- In `run_scenarios`: for each of `battery` / `location` / `network` present in the scenario, apply → verify → store the result.
- In `main`: wrap the run in `try … finally` so `restore()` runs **even if you press Ctrl+C**.

**Final run**
```bash
python3 emulator_control.py --package com.android.settings --wait 5
```

## Expected output

```
[+] Using emulator-5554
--- scenario: normal ---
[+] battery: requested 100% charging=True, read back {'level': 100, 'ac': True} -> confirmed
[*] location: lat=17.385 lon=78.4867 -> confirmed
[+] network speed full: console OK
[+] launched com.android.settings (foreground: yes)
--- scenario: low_battery ---
[+] battery: requested 5% charging=False, read back {'level': 5, 'ac': False} -> confirmed
...
[*] Restoring defaults
```

Then look inside `output/`:
- `results.jsonl`: one line per scenario (what was requested, what was confirmed, did the app start).
- `logcat/<scenario>.log`: what the app printed during that scenario.

## Check yourself (these become your report answers)

1. Why does GPS take **longitude first**? What happens if you swap them?
2. Why force-stop the app between scenarios?
3. Why is `"level: 5" in text` a bad battery check?
4. `adb shell dumpsys battery set level 5` and `adb emu power capacity 5` both change the reported level. One changes the phone's *report*, the other changes the *simulated hardware*. Which is closer to reality, and why?
5. Add a scenario of your own to `scenarios.json` (for example `very_slow_network`) **without touching the Python code**. What does that tell you about config files?

## Stuck?

| Problem | Try |
|---------|-----|
| `Need exactly one running emulator` | Close extra emulators, or pass `--device emulator-5554`. |
| `verify_battery` never succeeds | Print what `read_battery()` returns; check your regular expression. |
| App says `foreground: no` | It may have crashed; open `logcat/<scenario>.log` and look for `FATAL`. |
| Emulator left at 5% | Your `restore()` did not run; fix TODO 12 and 14. |

## Extension (optional)

Add device orientation (`adb emu rotate`) or an incoming call (`adb emu gsm call 5551234`) as a fourth condition, using a new key in `scenarios.json`.

## How this helps the assignment

The assignment's Task 2 asks for exactly this: at least two (you built three) conditions applied programmatically, verified, with the app run and behaviour recorded, and configurable scenarios. Copy your finished `emulator_control.py` and `scenarios.json` as the starting point of your submission, and describe the commands from the table above in your report.
