# Lab 4: Build a configurable API monitor

**Time:** 2 to 3 hours  **Difficulty:** ★★★☆☆
**Prepares you for:** Assignment **Task 3** (Configuration-Driven Frida API Monitor, 25 points, the biggest task)
**Do first:** Lab 3 and Demo 4. Lab 3 steps 1 to 4 are the building blocks you reuse here.

## What you will learn

- Turn the Lab 3 hooks into a **complete monitor**: full records (timestamp, class, method, arguments, return value, exception).
- Save results to a file in a **structured format** (JSON Lines).
- Write a small program that **summarises** the results, including APIs that never fired.

Unfamiliar word? See the [Glossary](../GLOSSARY.md).

## The big idea: three small programs working together

```
 apis.json ──▶ run_monitor.py ──▶ agent.js (inside the app) ──▶ one record per call
 (the list)    (on your laptop)                                        │
                     │◀──────────────── sends records ───────────────┘
                     ▼
               monitor.jsonl ──▶ summarize.py ──▶ readable summary
```

| Program | Where it runs | Its job |
|---------|---------------|---------|
| `agent.js` | inside the app | hook every API in the config; send a record for each call |
| `run_monitor.py` | your laptop | load the agent, give it the config, save every record to a file |
| `summarize.py` | your laptop | read the file and print counts and gaps |

**Records.** Each call becomes one JSON object:

```json
{"timestamp": 1763800000000, "category": "filesystem", "class": "java.io.File",
 "method": "exists", "signature": "", "args": [], "returnValue": "true", "exception": null}
```

**JSON Lines.** The file holds one such object **per line**. Why not one big list? Because if the program stops suddenly, every finished line is still safe and readable.

## Your task

All three programs are in `starter/` with numbered `TODO`s. Work in this order and test after each part.

> **First look at `apis.json`.** It is your config: each entry has a `category` (your own label), a `class` and a `method`. The assignment needs **at least 10 APIs from at least 4 categories**. The starter already has 11 from 7. Change it later; try adding your own.

---

### Part A: Hook everything in the config (`agent.js`, TODO 1)

`installHooks` loops over `config.hooks`. In TODO 1 you hook every method name of each entry. `method` may be a single name (`"exists"`) or a list (`["exists","delete"]`), so handle both.

> **Hint:**
> ```js
> var names = (typeof spec.method === "string") ? [spec.method] : spec.method;
> names.forEach(function (name) { hooks += hookMethod(klass, spec, name); });
> if (hooks > before) classes++;   // 'before' = hooks count before this class
> ```
> You did almost the same in Lab 3 step 4.

### Part B: Record each call (`agent.js`, TODO 2)

Inside `hookMethod`, replace each overload with a function that builds a record, calls the real method, fills in the answer, and `send()`s the record.

The order matters:

1. build the record (timestamp, category, class, method, signature, args)
2. call the real method inside `try { ... } catch (e) { ... }`
3. on success: set `returnValue`, `send(record)`, `return` the real result
4. on error: set `exception`, `send(record)`, then **`throw e`** (re-throw!)

> **Why re-throw?** If the app expected an error and your hook swallowed it, the app would behave differently while being watched. A monitor must not change the app.

> **Hint for the signature:** `overload.argumentTypes.map(function (t) { return t.className; }).join(", ")`
> **Hint for void methods:** `overload.returnType.className === "void"` → record `"void"`.

### Part C (stretch): The self-watching trap (`agent.js`, TODO 3)

Turning an argument into text calls `toString()`. If `toString()` itself calls a method you are monitoring (try adding `java.lang.StringBuilder` to the config), your hook calls itself forever and the app crashes.

Fix: keep a per-thread "I'm busy logging" flag; while it is set, pass calls straight through without logging. Try the crash first, then fix it. Compare with `solution/agent.js` (`busy`, `guarded`).

---

### Part D: Save records to a file (`run_monitor.py`, TODO 1 to 4)

- Open the output file (`monitor.jsonl`) for writing.
- In `on_message`, every record arriving from the agent is written as one line: `json.dumps(record) + "\n"`. Records that have an `"event"` key (like `"ready"`) are status messages: print them, do not save them.
- Connect to the device, attach to the app, load the agent, send it the config, wait for `--duration` seconds.
- In a `finally` block, clean up and print how many calls were recorded.

**Run (app open on the emulator, or leave `--attach` off to let the script start it):**
```bash
python3 run_monitor.py com.bootcamp.demoapp --attach --apis apis.json --duration 60 --out monitor.jsonl
```
**While it runs, use the app!** Open screens, change settings. Nothing happens, nothing is logged.

**Expected:**
```
[+] hooks installed: 11 methods across 7 classes
[12:01:03.221] filesystem   java.io.File.exists() -> true
...
[+] 143 calls recorded -> monitor.jsonl
```

**Checkpoint:** `head -n 3 monitor.jsonl` shows three lines of JSON.

### Part E: Summarise (`summarize.py`, TODO 1 to 5)

Read the file, then print:

1. calls **per category**
2. the **top 10 APIs** by number of calls
3. every call that raised an **exception**
4. which configured APIs **never fired**

> **Hint for TODO 1:** read line by line; skip empty lines; wrap `json.loads(line)` in `try/except ValueError` (a line may be cut off if the monitor was stopped abruptly).
> **Hint for counting:** `from collections import Counter` is already imported: `Counter(r["category"] for r in records).most_common()`.

**Test without a device**, using the sample log:
```bash
python3 summarize.py ../solution/sample/monitor_sample.jsonl --apis apis.json
```
**Expected (end of output):**
```
== Configured APIs that never fired ==
java.net.URL.openConnection
javax.crypto.Cipher.doFinal
...
```

## Check yourself (these become your report answers)

1. Why must the agent re-throw exceptions?
2. Why JSON Lines instead of one big JSON list?
3. Name one API in your config that never fired. Why might that be? (Not used by that app; it only runs on some screens; the class name is wrong; the class belongs to the app itself.)
4. `java.net.HttpURLConnection.connect` is *abstract*, so it never fires. What would you hook instead? (Try `java.net.URL.openConnection`.)
5. How did you add a new API? Did you touch the agent code? (You should not have.)

## Stuck?

| Problem | Try |
|---------|-----|
| `class not found, skipped` | Normal for classes missing on this Android version; check the spelling if it is one you expect. |
| `no such method` warning | Typo in the method name; names are case-sensitive. |
| Zero records | Use the app during the run; check hooks were installed (`[+] hooks installed: N`, N > 0). |
| App crashes after you add a class | Likely the self-watching trap (Part C). |
| `monitor.jsonl` is empty | Records are only written in `on_message`; add a `print` there to see if messages arrive. |

## How this helps the assignment

This lab **is** Task 3: a generic Frida script (`agent.js`), an API config file (`apis.json`), at least 10 APIs from at least 4 categories, overloads handled, and structured output for later processing. For your submission, run it on the assignment APK while exercising every screen, keep `monitor.jsonl` as evidence, and include the summary in your report.
