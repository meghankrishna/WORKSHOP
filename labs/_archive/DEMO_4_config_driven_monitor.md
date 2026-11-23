# Demo 4 (Instructor): One monitor, any list of APIs

**Time:** 20 minutes  **Supports:** Lab 4, Assignment Task 3 (the heavy one: 25 points)
**Students should leave knowing:** we change *what is monitored* by editing a config file, never the monitor, and results are saved in a file we can analyse.

## Before class

- Same setup as Demo 3 (emulator, frida-server, forwarded port, app open).
- `labs/lab4_api_monitor/solution/` open in a terminal.

## Steps

### 1. Show the config  (3 min)

Open `solution/apis.json`.
**Say:** "Each entry is just *which class, which method, and what category*. The assignment needs at least 10 entries and 4 categories. Categories are our own labels to group results."

### 2. Run it and use the app  (5 min)

**Run:**
```bash
python3 run_monitor.py com.bootcamp.demoapp --attach --apis apis.json --duration 40 --out monitor.jsonl
```
**Do:** in the Bootcamp Demo app, tap **Run ALL**, then try the buttons one at a time.
**Expect:**
```
[+] hooks installed: 11 methods across 7 classes
[12:01:03.221] filesystem   java.io.File.exists() -> true
[12:01:03.480] device_info  android.os.SystemProperties.get("ro.build.tags") -> "release-keys"
...
[+] 143 calls recorded -> monitor.jsonl
```
**Point out:** "It only saw what the app did. If nothing happens, nothing is logged. That is why the assignment says *use the app while monitoring*."

### 3. Look at the log file  (3 min)

**Run:**
```bash
head -n 3 monitor.jsonl
```
**Say:** "One call per line, each with timestamp, class, method, arguments, return value, exception. This file is what the report generator will read."

### 4. The big moment: add an API without touching code  (5 min)

Open `apis.json` in an editor and add one more entry to the list:
```json
{ "category": "package_info", "class": "android.app.ApplicationPackageManager", "method": "getPackageInfo" }
```
(Hook the concrete class `ApplicationPackageManager`, not the abstract `PackageManager`; abstract methods have no code of their own to hook.)
Re-run the same command.
**Expect:** new `package_info` lines appear.
**Say:** "I did not edit the monitor. That is the point of the assignment: *configurable and reusable*."

### 5. Summarise  (4 min)

**Run:**
```bash
python3 summarize.py monitor.jsonl --apis apis.json
```
**Point out:** calls per category, the busiest APIs, and **"Configured APIs that never fired"**. "Not every API is used by every app. Knowing which were silent is part of an honest report."

### 6. Optional: a richer run with the demo app  (5 min)

`apis.json` covers 11 APIs. For the finale, switch to `demo_apis.json`: 25 APIs in 10 categories, including location, database and package info (`demo-app/README.md` has the details). With the app open:
```bash
python3 run_monitor.py com.bootcamp.demoapp --attach --apis ../../../demo-app/demo_apis.json --duration 60 --out monitor.jsonl
```
Tap **Run ALL** in the app while it runs. **Say:** "One tap, nine behaviours: files, network, location, phone details, saved settings, database, encryption, a command, installed apps." Then:
```bash
python3 summarize.py monitor.jsonl --apis ../../../demo-app/demo_apis.json
```
**Point out:** 10 categories, about 90 calls, **"never fired: none"**, and under Exceptions the refused `getDeviceId` (a `SecurityException`). Switch Wi-Fi off, tap **2 Network**, and an `UnknownHostException` appears too.

## Why this matters for the assignment

This demo is the target: Lab 4 asks students to rebuild exactly this, in small steps.

## If it goes wrong

| Symptom | Fix |
|---------|-----|
| `class not found, skipped` for some entries | Normal: not every class exists on every Android version. Mention it, move on. |
| Very few calls | Tap through more screens; the app was idle. |
| `no such method` warnings | Method name typo in the config; show how the warning points to it. |
