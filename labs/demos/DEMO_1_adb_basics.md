# Demo 1 (Instructor): Talking to a phone from the command line

**Time:** 10 minutes  **Supports:** Lab 1, then Assignment Task 2
**Students should leave knowing:** the emulator is "just a program", and `adb` lets us give it commands from a script.

## Before class

- Emulator running and booted. Check: `adb devices` shows one `emulator-XXXX   device` line.
- Terminal font large enough for the back row. Emulator window visible next to the terminal.

## Steps

### 1. "Is there a phone?"  (2 min)

**Say:** "The emulator is a fake phone running on my laptop. `adb` is the remote control."
**Run:**
```bash
adb devices
```
**Expect:**
```
List of devices attached
emulator-5554   device
```
**Point out:** `emulator-5554` is the phone's name; `device` means it is ready. If it said `offline`, the phone is still booting.

### 2. "Ask the phone questions"  (3 min)

**Run:**
```bash
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop sys.boot_completed
```
**Say:** "`adb shell` means *run this command inside the phone*. `getprop` reads a phone setting."
**Expect:** a model name, an Android version number, and `1`.

### 3. "List apps, start an app"  (3 min)

**Run:**
```bash
adb shell pm list packages | head
adb shell monkey -p com.android.settings -c android.intent.category.LAUNCHER 1
```
**Point out:** the Settings app opens on the emulator screen. "Every app has a *package name*. We will use it to start and watch apps from code."

### 4. "Now from Python"  (2 min)

**Run:**
```bash
python3 -c "import subprocess; print(subprocess.run(['adb','shell','getprop','ro.product.model'], capture_output=True, text=True).stdout)"
```
**Say:** "Anything I can type in the terminal, a Python script can type for me. That is the whole trick behind our framework."

## Why this matters for the assignment

Task 2 is "control the emulator from a program". Everything in it is `adb` commands run by Python, plus reading the answers back.

## If it goes wrong

| Symptom | Fix |
|---------|-----|
| `adb: command not found` | `adb` is not on `PATH`; run it by its full path. |
| `no devices/emulators found` | Emulator still starting or closed. Wait for the home screen. |
| `device offline` | `adb kill-server` then `adb devices`. |
