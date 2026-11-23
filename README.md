# Bootcamp Run Sheet: commands for demos, labs and assignment

Every command you need, in the order you need them. Run everything from this folder (`BOOTCAMP/`) unless a step says otherwise. Written for the instructor; students run the same commands in the lab steps.

| Part | Where to start |
|------|----------------|
| Get the environment ready (every session) | [Section 1](#1-start-the-environment-every-session) |
| Instructor demos 1 to 4 | [Section 2](#2-instructor-demos) |
| Student labs 1 to 4 | [Section 3](#3-student-labs) |
| Assignment tasks | [Section 4](#4-assignment) |
| Shut down | [Section 5](#5-shut-down) |
| Something broke | [Section 6](#6-troubleshooting) |

Slides: `labs/Android_Dynamic_Analysis_Intro.pptx`. Word list: `labs/GLOSSARY.md`.

---

## 0. One-time preparation

`setup.sh` has already been run successfully, so the emulator (`pixel-29`), the Python environment (`venv/`) and `frida-server` exist. Two small extras remain.

**a) Check the system packages** (read-only, needs no sudo):
```bash
./check_packages.sh
```
It must end with `RESULT: READY`.

**b) Install the Frida Java bridge for the labs.** Frida 17 does not include it, and Lab 3 needs it. This downloads one small package into `labs/`:
```bash
./venv/bin/python3 -c "
import frida
r = frida.PackageManager().install(specs=['frida-java-bridge'], project_root='labs')
print([(p.name, p.version) for p in r.packages])"
```
Expected: `[('frida-java-bridge', '...')]`. Needs internet. (`api_monitor.py` in this folder installs the bridge for itself on first run.)

---

## 1. Start the environment (every session)

Do these four steps at the start of every class.

```bash
# 1. Use the project's Python (has frida installed)
source venv/bin/activate

# 2. Make adb available in this terminal
export PATH="$HOME/Android/Sdk/platform-tools:$HOME/Android/Sdk/emulator:$PATH"

# 3. Start the emulator and wait until it has booted
./setup.sh start

# 4. Start frida-server on the emulator and forward its port
./setup.sh frida-start
```

**Check it worked:**
```bash
adb devices                 # shows: emulator-5554   device
frida-ps -Ua                # lists the apps running on the phone (proves Frida can reach it)
./setup.sh frida-status     # Server: running
```

Optional: for a clean, repeatable starting point, use the saved snapshot instead of step 3, then repeat step 4:
```bash
./setup.sh snapshot-load analysis-clean
./setup.sh frida-start
```

> The Frida scripts below find the emulator through `adb` automatically, so you never type a Frida address yourself. If a script cannot find the device, see [Troubleshooting](#6-troubleshooting).
>
> `./setup.sh frida-start` can print "Frida server failed to start" even though the server did start (its 30-second check gives up early on a slow first start). Run `frida-ps -Ua`: if it lists apps, Frida is fine and you can carry on. Otherwise run `./setup.sh frida-start` once more.

### Install a test app (once)
```bash
./setup.sh install-apk /path/to/assignment.apk
adb shell pm list packages | grep -i <part-of-the-name>      # find its package name
```
The Frida demos and labs use the **Bootcamp Demo** app, because it reliably triggers every call we monitor (the built-in Settings app is too quiet to demo with). Install it once:
```bash
adb install -r demo-app/bootcamp-demo.apk
adb shell pm grant com.bootcamp.demoapp android.permission.ACCESS_FINE_LOCATION
adb shell pm grant com.bootcamp.demoapp android.permission.READ_PHONE_STATE
```
Details: [demo-app/README.md](demo-app/README.md). Labs 1 and 2 and Demos 1 and 2 still use the built-in Settings app.

---

## 2. Instructor demos

Full talk-track for each demo is in `labs/demos/`. These are just the commands.

### Demo 1: adb basics
Script: `labs/demos/DEMO_1_adb_basics.md`
```bash
adb devices
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop sys.boot_completed
adb shell pm list packages | head
adb shell monkey -p com.android.settings -c android.intent.category.LAUNCHER 1
python3 -c "import subprocess; print(subprocess.run(['adb','shell','getprop','ro.product.model'], capture_output=True, text=True).stdout)"
```

### Demo 2: emulator console
Script: `labs/demos/DEMO_2_emulator_console.md`. Open Settings, then **Battery**, on the emulator first.
```bash
adb emu power capacity 5
adb emu power ac off
adb emu power status discharging
adb shell dumpsys battery                        # verify: level: 5, AC powered: false

adb emu power capacity 50                        # the classic bug:
adb shell dumpsys battery | grep "level: 5"      #   this also matches level: 50

adb emu geo fix 78.4867 17.385                   # longitude FIRST, then latitude
adb emu network speed edge
adb emu network status
adb emu network speed full
```
Reset afterwards:
```bash
adb emu power ac on
adb emu power status charging
adb emu power capacity 100
adb emu network speed full
```

### Demo 3: first Frida hook
Script: `labs/demos/DEMO_3_frida_first_hook.md`. Open the **Bootcamp Demo** app on the emulator first:
`adb shell monkey -p com.bootcamp.demoapp -c android.intent.category.LAUNCHER 1`
```bash
cd labs/lab3_frida_first_hooks
python3 run_frida.py com.bootcamp.demoapp solution/step1_hello.js --duration 20
python3 run_frida.py com.bootcamp.demoapp solution/step2_args_and_result.js --duration 20
python3 run_frida.py com.bootcamp.demoapp solution/step3_overloads.js --duration 20
python3 run_frida.py com.bootcamp.demoapp solution/step4_config_driven.js --config apis_demo.json --duration 30
cd ../..
```
While each one runs, tap **1 Files**, **2 Network** and **Run ALL** in the app; you only see what the app does.

### Demo 4: strace (system calls)
Script: `labs/demos/DEMO_4_strace.md`. Open the **Bootcamp Demo** app first. strace is already on the emulator and runs as root, so no setup is needed.
```bash
PID=$(adb shell pidof com.bootcamp.demoapp | tr -d '\r')
adb shell "su -c 'timeout -s INT 30 strace -f -tt -s 96 -e trace=openat,faccessat,connect,execve -o /data/local/tmp/demo.txt -p $PID'"
```
While it runs, tap **1 Files**, **5 Saved settings**, **6 Database**, **2 Network** and **8 Run a command**. Then show the results:
```bash
adb shell su -c "cat /data/local/tmp/demo.txt" | grep "com.bootcamp.demoapp"    # files
adb shell su -c "cat /data/local/tmp/demo.txt" | grep "connect"                  # network
adb shell su -c "cat /data/local/tmp/demo.txt" | grep "execve"                   # programs started
```
Do not run Frida on the same app at the same time: two tools cannot attach to one process.

---

## 3. Student labs

Students work in each lab's `starter/` folder (with the TODOs); `solution/` is for you. Each lab's `LAB.md` has the full instructions. Always do Section 1 first.

| Lab | Folder | Students edit | Run |
|-----|--------|---------------|-----|
| **1** adb from Python | `labs/lab1_adb_from_python/` | `starter/adb_basics.py` | `cd labs/lab1_adb_from_python/starter && python3 adb_basics.py` |
| **2** Emulator control | `labs/lab2_emulator_control/` | `starter/emulator_control.py` | `cd labs/lab2_emulator_control/starter && python3 emulator_control.py --package com.android.settings --wait 5` |
| **3** First Frida hooks | `labs/lab3_frida_first_hooks/` | the `.js` files in `starter/` | `python3 run_frida.py com.bootcamp.demoapp starter/step1_hello.js --duration 20` (from the lab folder) |
| **4** strace | `labs/lab4_strace/` | `starter/strace_capture.py`, `starter/strace_parse.py` | see below |

Lab 4 student run (from `labs/lab4_strace/starter/`, app open on the emulator):
```bash
python3 strace_capture.py com.bootcamp.demoapp --duration 30 --out raw_strace.log     # tap the app's buttons while it runs
python3 strace_parse.py raw_strace.log --out events.jsonl
```
No emulator handy? The parser works on a bundled real capture:
```bash
python3 strace_parse.py ../solution/sample/strace_sample.log --out events.jsonl
```

To show the finished answer for any lab, run the same command from its `solution/` folder instead of `starter/`. Lab 2 results land in `output/results.jsonl` and `output/logcat/` inside the folder you ran it from.

---

## 4. Assignment

The finished framework files sit in this folder: `emulator_control.py`, `api_monitor.py`, `frida_hook_generator.js` and the settings in `Config/`. Students build their own versions using the labs. Replace `<package>` with the assignment app's package name (for example `jakhar.aseem.diva`).

### Emulator detection sample app
`detector.apk` is the sample detector app (package `com.reveny.emulator.detection.sample`). To install and open it:
```bash
./setup.sh install-apk detector.apk
adb shell monkey -p com.reveny.emulator.detection.sample -c android.intent.category.LAUNCHER 1
```
It lists what it detects on the emulator screen. The detection-mitigation work for Task 1 is not covered in this run sheet.

### Task 2: emulator environment control
Scenarios (battery, GPS, network) are defined in `Config/emulator_config.json`.
```bash
python3 emulator_control.py <package> --wait 15
```
- `--device emulator-5554` picks a specific emulator (it is auto-detected by default).
- `--config <file>` uses a different scenario file; `--debug` prints every raw `adb` command.
- Results: `Output/emulator_scenario_log.txt` (readable) and `Output/emulator_scenario_log.jsonl` (structured).
- The emulator is reset to normal when the run ends, even after Ctrl+C.

### Task 3: configuration-driven API monitor
APIs to monitor are listed in `Config/api_config.json` (11 APIs, 7 categories).
```bash
python3 api_monitor.py <package>              # starts the app and monitors it (recommended)
python3 api_monitor.py <package> --stack      # also record a Java stack trace per call
python3 api_monitor.py "<App Name>" --attach  # monitor an app that is already open
```
- `--attach` needs the name `frida-ps -Ua` shows in its **Name** column (for example `"Settings"`), not the package name. Starting the app (the first form) takes the package name and avoids this.
- **Use the app while it runs.** Nothing happens, nothing is logged. Press **Ctrl+C** to stop; the run has no timer.
- Results: `Output/api_monitor_logs.jsonl`, one JSON record per line.
- The first run downloads the Frida Java bridge into this folder (needs internet).

### System-call monitoring (strace)
Use the lab's tools on the assignment app (open it first):
```bash
cd labs/lab4_strace/solution
python3 strace_capture.py <package> --duration 60 --out raw_strace.log     # use the app while it runs
python3 strace_parse.py raw_strace.log --out events.jsonl
cd ../../..
```
Which calls are recorded is controlled by `labs/lab4_strace/solution/strace_config.json`. Keep `raw_strace.log` and `events.jsonl` as evidence.

### Putting the evidence together
Run Task 2 and Task 3 against the assignment app, then keep these as evidence for the report:
```
Output/emulator_scenario_log.txt
Output/emulator_scenario_log.jsonl
Output/api_monitor_logs.jsonl
```

---

## 4b. Demo app: one app that does everything

`demo-app/bootcamp-demo.apk` is a harmless app with a button for each thing we monitor (files, network, location, phone info, saved settings, database, encryption, running a command, installed apps) and a live panel for battery, location and network. Use it to show an app *doing* things and the monitor *catching* them. Full walkthrough: [demo-app/README.md](demo-app/README.md).

```bash
adb install -r demo-app/bootcamp-demo.apk
adb shell pm grant com.bootcamp.demoapp android.permission.ACCESS_FINE_LOCATION
adb shell pm grant com.bootcamp.demoapp android.permission.READ_PHONE_STATE
adb shell monkey -p com.bootcamp.demoapp -c android.intent.category.LAUNCHER 1
```
Monitor it with the assignment framework (it starts the app itself; tap **Run ALL** and press Ctrl+C when done):
```bash
python3 api_monitor.py com.bootcamp.demoapp --config demo-app/demo_apis.json
```
A typical run catches about 80 calls from all 25 configured APIs in 10 categories (results in `Output/api_monitor_logs.jsonl`). To see the same app at the system-call level, use the strace demo and Lab 4 above.

---

## 5. Shut down

```bash
./setup.sh frida-stop
./setup.sh stop
deactivate          # leave the Python environment
```

---

## 6. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `adb: command not found` | Run the `export PATH=...` line from Section 1 in this terminal. |
| `adb devices` shows nothing or `offline` | The emulator is still booting. Wait for the home screen, or `adb kill-server && adb devices`. |
| `./setup.sh start` stops with missing packages | Run `./check_packages.sh` and send the missing-package list to your administrator. |
| Frida: `unable to connect` / `server not running` | Run `./setup.sh frida-start` again. It must be repeated after every emulator restart or `snapshot-load`. |
| Frida: `unable to find process` or `... is not running` | The app is not open. Open it, then check it appears in `frida-ps -Ua` (Frida lists apps by display name; the lab scripts match on the package name in the **Identifier** column). |
| Lab 3: `frida-java-bridge not found` | Do step 0b (install the Java bridge) once. |
| strace: `su: not found`, or `Operation not permitted` | The emulator is not rooted (`./setup.sh verify` should say `Root: available`), or Frida is attached to the same app. Stop Frida and restart the app. |
| strace output file is empty | You tapped the app before or after the trace. Tap its buttons while strace is running. |
| Frida host and server versions differ | `./setup.sh frida-start` re-installs the matching server. Check with `./setup.sh frida-status`. |
| Monitor shows few or no calls | The app was idle. Tap through more screens while it runs. |
| `emulator_control.py`: `Need exactly one running emulator` | Close extra emulators, or pass `--device emulator-5554`. |
| Emulator stuck at 5% battery | A run was killed before it could reset. Run the reset commands from Demo 2. |
| Battery in the app/`dumpsys` ignores `adb emu power ...` | Known emulator quirk: the console changes the virtual hardware but Android stops noticing. Use the override instead: `adb shell dumpsys battery set level 5` and `adb shell dumpsys battery unplug`; undo with `adb shell dumpsys battery reset`. `emulator_control.py` does this fallback for you. To make Android re-read the real value: `adb shell su -c "stop vendor.health-hal-2-0"` then `adb shell su -c "start vendor.health-hal-2-0"`. |
| Everything is a mess | `./setup.sh stop`, then `./setup.sh snapshot-load analysis-clean`, then `./setup.sh frida-start`. |
