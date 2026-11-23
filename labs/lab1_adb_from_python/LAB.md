# Lab 1: Talk to the emulator from Python

**Time:** 30 minutes  **Difficulty:** ★☆☆☆☆ (start here)
**Prepares you for:** Assignment Task 2 (controlling the emulator from code)

## What you will learn

- Run a command-line tool (`adb`) from a Python script.
- Read its answer and pull out the part you need.
- Write one small helper you will reuse in every later lab.

Unfamiliar word? See the [Glossary](../GLOSSARY.md). Watch **Demo 1** first.

## The big idea

Whatever you type in the terminal, Python can type for you:

```python
import subprocess
result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
print(result.stdout)
```

`result.stdout` is the text the command printed. Each word of the command is a separate item in the list.

## Your task

Open `starter/adb_basics.py`. It has four small functions with `TODO`s. Fill them in one at a time and test after each.

| # | Function | Does | Example result |
|---|----------|------|----------------|
| 1 | `run_adb(*args)` | Runs `adb <args>` and returns the text it printed | `"List of devices attached\n..."` |
| 2 | `list_emulators()` | Returns serial names of ready emulators | `["emulator-5554"]` |
| 3 | `get_prop(serial, name)` | Reads one phone setting | `get_prop("emulator-5554","ro.product.model")` → `"sdk_gphone_x86"` |
| 4 | `describe_device(serial)` | Returns a dict with model, android version, boot state | `{"model": "...", "android": "10", "booted": True}` |

## Step by step

### Step 1: run any adb command
Fill in `run_adb`.
> **Hint:** `subprocess.run(["adb", *args], capture_output=True, text=True)`, then return `.stdout.strip()`.

**Test it:**
```bash
python3 -c "from adb_basics import run_adb; print(run_adb('devices'))"
```
You should see the same text as typing `adb devices`.

### Step 2: find the emulator
`adb devices` prints a header and then one line per phone:
```
List of devices attached
emulator-5554   device
```
Skip the first line, split each line into words, keep the ones where the second word is `device` and the first starts with `emulator-`.
> **Hint:** `line.split()` turns `"emulator-5554   device"` into `["emulator-5554", "device"]`.

**Test it:** `python3 -c "from adb_basics import list_emulators; print(list_emulators())"` → `['emulator-5554']`

### Step 3: read a phone setting
`adb -s emulator-5554 shell getprop ro.product.model` asks one phone for one setting. `-s` chooses *which* phone.

**Test it:** `python3 adb_basics.py` runs a small self-check at the bottom of the file.

### Step 4: combine them
Use `get_prop` three times: `ro.product.model`, `ro.build.version.release`, `sys.boot_completed` (it is the text `"1"` once the phone is ready).

## Expected output of the final self-check

```
Emulators found: ['emulator-5554']
Device info: {'model': 'sdk_gphone_x86', 'android': '10', 'booted': True}
```

## Check yourself

1. What happens if you run `run_adb("nonsense")`? Read the message, then think about why a script should show errors rather than hide them.
2. What does `-s emulator-5554` do, and when would you need it?
3. Why do we use `.strip()` on the output?

## Stuck?

- `FileNotFoundError: adb` means Python cannot find `adb`; ask your instructor.
- Empty list from `list_emulators()`? Run `adb devices` in a terminal. If it shows nothing, the emulator is not running.
- Print things! `print(repr(text))` shows hidden characters like `\n`.

## How this helps the assignment

Every part of Task 2 is "run an adb command, read the answer". The `run_adb` helper you wrote here is the same building block used in Lab 2.
