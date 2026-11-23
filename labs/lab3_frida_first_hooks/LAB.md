# Lab 3: Your first Frida hooks

**Time:** 90 minutes  **Difficulty:** ★★☆☆☆
**Prepares you for:** Assignment **Task 3** (config-driven API monitor, 25 points). Lab 4 then moves one level down, to system calls (strace).
**Do first:** Demo 3 (watch the instructor hook a function).

## What you will learn

- What a **hook** is, and how to write one in a few lines.
- How to see a function's **arguments** and **return value**.
- What **overloads** are, and how to hook all of them.
- How to read the list of functions to hook from a **config file**.

In this lab we only **watch**. Your hooks always call the real function and pass its real answer back, so the app behaves exactly as normal.

Unfamiliar word? See the [Glossary](../GLOSSARY.md).

## The big idea

```
 App code ──calls──▶ File.exists("/sdcard/x") ──▶ answer
                            ▲
                      your hook sits here:
                      "write it down, then pass it on"
```

Frida lets you replace a Java method with your own function. Your function writes a note and then calls the original.

## How to run any step

1. Open the **Bootcamp Demo** app on the emulator (it is already installed).
2. In a terminal, in this lab folder:
   ```bash
   python3 run_frida.py com.bootcamp.demoapp starter/step1_hello.js --duration 20
   ```
   (`run_frida.py` is provided. You never edit it. It loads your `.js` file into the app and prints what it says.)
3. **Use the app** while it runs: tap **1 Files**, **2 Network** and **Run ALL**. You only see what the app does.
4. When your step works, compare with `solution/` (only after you tried!).

> You only edit the `.js` files in `starter/`.

---

## Step 1: Hello, hook!  (`starter/step1_hello.js`)

**Goal:** print a line every time the app calls `File.exists()` ("does this file exist?").

Open the file. You will see a `TODO`. Write the replacement function. The three-line recipe is in the comments:
call the real method, print a message, return the real answer.

**Run:**
```bash
python3 run_frida.py com.bootcamp.demoapp starter/step1_hello.js --duration 20
```
**Expected output:** (many lines while you tap)
```
hook installed on File.exists
File.exists() was called
File.exists() was called
...
```

**Why return the real answer?** If you forget `return answer;` the app receives nothing and may misbehave. A good monitor must not change what the app sees.

---

## Step 2: Arguments and results  (`starter/step2_args_and_result.js`)

**Goal:** print *which file* was asked about and *what the answer was*.

`this` inside your function is the File object. `this.getPath()` gives its path.

**Expected output:**
```
File.exists("/data/user/0/com.bootcamp.demoapp/files") -> true
File.exists("/system/etc/foo.conf") -> false
```

**Think:** which lines are `false`? These are files the app looked for and did not find. Malware analysts care about that.

---

## Step 3: Overloads  (`starter/step3_overloads.js`)

**Goal:** hook *every version* of `android.util.Log.d`.

Many methods exist in several versions with the same name. These are **overloads**. For `Log.d`:
- `d(String tag, String message)`
- `d(String tag, String message, Throwable error)`

A hook must pick a version, or hook all of them. The starter already loops over `Log.d.overloads`. You fill in what happens inside.

**Expected output:** first the setup lines, then one per call:
```
hooking Log.d(java.lang.String, java.lang.String)
hooking Log.d(java.lang.String, java.lang.String, java.lang.Throwable)
Log.d(java.lang.String, java.lang.String) args: ActivityThread | handleBindApplication
```

**Think:** what would happen if you only hooked one version? Which calls would you miss?

---

## Step 4: A config file  (`starter/step4_config_driven.js`)

**Goal:** hook whatever is listed in `apis_demo.json`, **without changing the code** when the list changes.

```json
{ "hooks": [ {"class": "java.io.File", "method": "exists"},
             {"class": "android.util.Log", "method": "d"} ] }
```

`hookOne(...)` is already written (it is steps 2 and 3 combined). You:
1. print one line per call in the `TODO` inside `hookOne`
2. loop over `config.hooks` and call `hookOne` for each entry

**Run (note the extra `--config`):**
```bash
python3 run_frida.py com.bootcamp.demoapp starter/step4_config_driven.js --config apis_demo.json --duration 30
```
**Expected output:**
```
hooked java.io.File.exists
hooked android.util.Log.d
java.io.File.exists() -> true
android.util.Log.d(java.lang.String, java.lang.String) -> 3
```

**Now the key experiment:** add `{"class": "java.net.URL", "method": "$init"}` to `apis_demo.json` and run again. Did you edit any JavaScript? That is the idea behind Assignment Task 3.

> `$init` is Frida's name for a **constructor** (the code that creates a new object).

---

## Check yourself

1. In step 1, what happens to the app if your hook forgets to `return answer`?
2. What is an overload? Give an example from this lab.
3. Why is a config file better than writing a new hook for each function?
4. A function in your config is never printed. Give two possible reasons.

## Stuck?

| Problem | Try |
|---------|-----|
| `... is not running` | The app is not open. Open it, then check it is listed by `frida-ps -Ua` (the package name is in the **Identifier** column). |
| Nothing printed | Tap around in the app. Quiet apps call few functions. |
| `[error] ... is not a function` | Check spelling; JavaScript is case-sensitive (`getPath`, not `getpath`). |
| `ambiguous` / `overload` error | You hooked a method that has overloads without choosing one; use the loop from step 3. |
| Connection errors | Tell your instructor: Frida server may not be running. |

## How this helps the assignment

Task 3 asks for a **generic** monitor driven by a config file that records timestamp, class, method, arguments, return value and exceptions, and handles overloads. Steps 1 to 4 give you every building block: a hook, arguments and return values, overloads, and a config file. For the assignment you extend step 4 yourself: record a timestamp, the class and method, the arguments, the return value and any exception for each call, and save the records to a file as JSON Lines (one record per line, the format you meet again in Lab 4). A finished reference for that extension is in `_archive/lab4_api_monitor/` (instructors only).
