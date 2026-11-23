# Bootcamp Labs: Android Dynamic Analysis for Beginners

No prior knowledge of Android tooling is needed. The instructor demonstrates each idea first (**demos**), you practise it in a small **lab**, and the labs together prepare you for the **assignment**.

```
 Demo 1 → Lab 1 ─┐
 Demo 2 → Lab 2 ─┴─▶ Assignment: control the emulator
 Demo 3 → Lab 3 ───▶ Assignment: configurable Frida API monitor (warm-up)
 Demo 4 → Lab 4 ───▶ Assignment: system-call monitoring with strace
```

## The path

| Step | Instructor demo | Student lab | What you can do afterwards |
|------|-----------------|-------------|----------------------------|
| 1 | [Demo 1: adb basics](demos/DEMO_1_adb_basics.md) | [Lab 1: adb from Python](lab1_adb_from_python/LAB.md) | Run commands on the emulator from a Python script |
| 2 | [Demo 2: emulator console](demos/DEMO_2_emulator_console.md) | [Lab 2: emulator control](lab2_emulator_control/LAB.md) | Change battery/GPS/network, verify, launch the app, record, restore |
| 3 | [Demo 3: first Frida hook](demos/DEMO_3_frida_first_hook.md) | [Lab 3: first Frida hooks](lab3_frida_first_hooks/LAB.md) | Hook a method, log arguments/results, handle overloads, read a config |
| 4 | [Demo 4: strace](demos/DEMO_4_strace.md) | [Lab 4: strace](lab4_strace/LAB.md) | Capture an app's system calls, parse them into JSON Lines, summarise them |

Stuck on a word? Read the [Glossary](GLOSSARY.md). A harmless app to demonstrate with, `demo-app/bootcamp-demo.apk`, lives one folder up (see `../demo-app/README.md`).

## How each assignment requirement is covered

| Assignment requirement | Where you practise it |
|------------------------|-----------------------|
| Run commands on the emulator programmatically | Lab 1, Lab 2 |
| Emulator conditions (battery, GPS, network) via code, not the GUI | Lab 2 Parts 2 and 3 |
| Verify each change was applied | Lab 2 Parts 2 and 3 |
| Run the app and record its behaviour | Lab 2 Part 4 |
| Configurable scenario parameters | Lab 2 (`scenarios.json`) |
| Hook Java APIs with Frida, no hand-written hook per API | Lab 3 steps 1 to 4 (you extend step 4 in the assignment) |
| Handle method overloading | Lab 3 step 3 |
| Read the APIs to monitor from a config file | Lab 3 step 4 |
| Monitor native / system-level operations (system calls) | Lab 4 (strace) |
| Choose what to record through a config file | Lab 4 (`strace_config.json`) |
| Structured output (JSON Lines) for later processing | Lab 4 Part C |

Not covered by these labs: the emulator-detection task, and the full Frida API-monitor build (timestamp, class, method, arguments, return value, exception, saved to a file). Lab 3 gives the building blocks for the latter.

## Folder layout

```
labs/
├── GLOSSARY.md                  plain-language word list
├── Android_Dynamic_Analysis_Intro.pptx   slides for the introduction
├── demos/                       instructor scripts (what to say, run, expect)
├── lab1_adb_from_python/        LAB.md + starter/ (TODOs) + solution/
├── lab2_emulator_control/       LAB.md + starter/ + solution/
├── lab3_frida_first_hooks/      LAB.md + run_frida.py + apis_demo.json + starter/ + solution/
├── lab4_strace/                 LAB.md + starter/ + solution/ (with a real sample capture)
└── _archive/                    the earlier Frida API-monitor demo and lab (instructor reference)
```

Students work only in `starter/`. Instructors keep `solution/` private until the lab ends.

## Environment

The labs assume the machine is already prepared: a running **rooted** Android emulator, `adb`, Frida with a matching server on the emulator, the Java bridge for Frida, `strace` on the emulator (it ships with the image), and the demo app installed. There are no setup steps in the labs.

## Instructor note

Tested on the `pixel-29` emulator: the Lab 2 solution, the Lab 3 runner with steps 2 and 4, the strace demo commands, and the Lab 4 solution (capture and parse). The Lab 1 solution was tested against a simulated `adb`. Not tested: the Lab 3 steps 1 and 3 individually, and the starters (they were checked only for syntax and for failing cleanly at the first TODO).
