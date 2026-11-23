# Demo 2 (Instructor): Changing the fake phone's world

**Time:** 20 minutes  **Supports:** Lab 2, Assignment Task 2
**Students should leave knowing:** the emulator can fake battery, location and network from commands, a good tool *reads the value back* to prove it worked, and a *scenario* is just a named bundle of those commands kept in a config file.

## Before class

- Emulator running, Settings app open on the **Battery** screen.
- Optional: the Maps app open (for the location part).
- Second terminal ready.

## Steps

### 1. Battery: something visible  (5 min)

**Say:** "The emulator has a console, a control panel for the fake phone itself. `adb emu` talks to it."
**Run, one at a time, letting the room watch the emulator screen:**
```bash
adb emu power capacity 5
adb emu power ac off
adb emu power status discharging
```
**Expect:** each prints `OK`; the battery indicator on the emulator drops to 5% and shows "not charging".

**Now prove it from the phone's side:**
```bash
adb shell dumpsys battery
```
**Point out the lines** `AC powered: false` and `level: 5`.

**Say:** "I did not trust the `OK`. I *asked the phone* what its battery is. That is called **verifying**, and the assignment asks for it."

> **If `dumpsys battery` still shows the old level:** this emulator sometimes keeps the console change in the virtual hardware and never tells Android. Test it before class. Fallback that always works: `adb shell dumpsys battery set level 5` and `adb shell dumpsys battery unplug` (undo: `adb shell dumpsys battery reset`). It makes a good teaching moment: "the OK came from the emulator, but I verify what *Android* sees, and sometimes they disagree."

### 2. The classic bug  (2 min)

**Say:** "A tempting shortcut is to check `'level: 5' in output`. Let me show why that is wrong."
**Run:**
```bash
adb emu power capacity 50
adb shell dumpsys battery | grep "level: 5"
```
**Expect:** it matches `level: 50` even though we asked for 5.
**Say:** "Match the *whole line* instead (a regular expression). This is exactly the bug Lab 2 asks you to avoid."

### 3. Location  (4 min)

**Run:**
```bash
adb emu geo fix 78.4867 17.385
```
**Point out:** **longitude first, then latitude**, the opposite of how people say it. Open Maps: the blue dot moves to Hyderabad. Swap the numbers on purpose to show the dot jumping to the wrong place, then fix it.

### 4. Network  (2 min)

**Run:**
```bash
adb emu network speed edge
adb emu network status
adb emu network speed full
```
**Say:** "Edge is a very slow old mobile network. Apps behave differently on slow networks. Remember to set it back."

> **Heads-up:** on this emulator the speed setting is accepted (`network status` shows it) but pages still load at normal speed, so students will not *see* an effect. To show a network condition that is visible, switch the network off instead (works well with `demo-app/bootcamp-demo.apk`):
> ```bash
> adb shell svc wifi disable; adb shell svc data disable     # app: UnknownHostException
> adb shell svc wifi enable;  adb shell svc data enable      # back to normal
> ```

### 5. Reset  (2 min)

**Run:**
```bash
adb emu power ac on
adb emu power status charging
adb emu power capacity 100
adb emu network speed full
```
**Say:** "Always put things back. Our program must do this *even if it crashes*."

### 6. From commands to a scenario  (5 min)

This is the bridge to the lab. Students have just watched you type commands by hand; now show that a scenario is those same commands, written down once.

**Say:** "I just typed about ten commands. If I wanted to repeat 'the phone is almost dead' for ten different apps, I would type them ten times. So we write the situation down once and give it a name. That name plus its settings is called a **scenario**."

**Show on screen** the lab's config file:
```bash
cat ../lab2_emulator_control/solution/scenarios.json
```

**Walk through it by matching each scenario to commands students already saw:**

| Scenario name | What it means | The commands you typed earlier |
|---------------|---------------|--------------------------------|
| `normal` | everything healthy | `power capacity 100`, `power ac on`, `geo fix 78.4867 17.385`, `network speed full` |
| `low_battery` | phone almost dead | `power capacity 5`, `power ac off`, `power status discharging` |
| `different_location` | phone is in Tokyo on a slow network | `geo fix 139.6917 35.6895`, `network speed edge` |

**Say:** "The file is just a list of situations. The program reads it and runs the matching commands for each one. To add a new situation I edit the file. I never touch the code. That is what the assignment means by *configurable scenarios*."

**Show the loop** (draw it, or point at the Lab 2 page):
```
 set conditions → verify them → restart the app → wait → save what happened → (at the end) reset
```
**Say:** "Every step is something you did by hand in this demo. In the lab you teach Python to do the same loop for you."

**Run the finished version once** so they see the goal before they build it (Settings app, 5 s per scenario):
```bash
cd ../lab2_emulator_control/solution
python3 emulator_control.py --package com.android.settings --wait 5
cd ../../demos
```
**Point out** as it runs: each scenario prints `confirmed` for the battery (the verify step), the app restarts each time, and the last line is `Restoring defaults`. Then open `output/results.jsonl` and show one line per scenario: "this is the record the assignment asks for".

**Tell them:** "In the lab you build this one piece at a time, and you test after every piece. You do not have to write it all at once."

## Why this matters for the assignment

Task 2 asks for: change conditions from code, verify each change, run the app, record behaviour, with scenarios that are configurable. This demo shows the commands, the verification idea, and what a scenario file looks like; Lab 2 turns it into a script.

## If it goes wrong

| Symptom | Fix |
|---------|-----|
| `KO: unknown command` | Typo in the console command; compare with the lines above. |
| Battery on screen does not change | Look at `dumpsys battery`, not the icon; some images update slowly. |
| `geo fix` runs but Maps does not move | Give it a few seconds, or tap the "my location" button. |
