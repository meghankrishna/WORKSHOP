# Lab 4: strace: record the system calls of an app

**Time:** 2 hours  **Difficulty:** ★★★☆☆
**Prepares you for:** the assignment work on native / system-level monitoring (system calls) and on storing what you collect in a structured format
**Do first:** Demo 4 (the instructor shows strace live) and Lab 3 (JSON Lines).

## What you will learn

- What a **system call** is, and how `strace` records them.
- How to run `strace` on an app from a Python script, using settings from a **config file**.
- How to turn raw `strace` text into **structured events** (JSON Lines) and a readable summary.

Unfamiliar word? See the [Glossary](../GLOSSARY.md).

## The big idea

An app cannot touch a file, the network or another program by itself. It asks the kernel with a **system call**. `strace` writes down every such request.

```
 Java code in the app            <- Frida (Lab 3) watches here
   │
 ───────────────────────────────
 system calls: openat, connect   <- strace (this lab) watches here
 ───────────────────────────────
   │
 Linux kernel
```

Your toolchain has two small programs:

```
 strace_config.json ──▶ strace_capture.py ──▶ raw_strace.log ──▶ strace_parse.py ──▶ events.jsonl + summary
 (which calls to watch)  (runs strace on the     (raw text)        (turns text into     (structured, ready for
                          phone, pulls the log)                      records)             the report)
```

## The calls you will meet

| System call | What it means | Java action behind it |
|-------------|---------------|-----------------------|
| `openat` | open (or create) a file | `FileOutputStream`, `FileInputStream`, saved settings, databases |
| `faccessat` | does this file exist? | `File.exists()` |
| `connect` | connect to an address (or local socket) | opening a web page |
| `execve` | start another program | `Runtime.exec(...)` |

A line of raw strace output looks like this:

```
10350  17:16:10.525595 faccessat(AT_FDCWD, "/data/local/tmp/does-not-exist", F_OK) = -1 ENOENT (No such file or directory)
pid    time            syscall(arguments ...............................)           = result  error name
```

`= 0` or a positive number means success. `= -1 ENOENT` means it failed because the file does not exist.

## Files

- `starter/strace_capture.py`: runs strace and fetches the log (TODO 1 to 4)
- `starter/strace_parse.py`: parses the log (TODO 1 to 5)
- `starter/strace_config.json`: which calls to watch (you do not edit it, but read it)
- `solution/`: instructor answers, plus `solution/sample/strace_sample.log`, a real capture to practise on without a phone

> Work inside `starter/`. Part B needs the emulator and the **Bootcamp Demo** app open. Part C and D can be done with the sample log.

---

## Part A: See it by hand (15 minutes)

Do this first so the program in Parts B and C makes sense. Open the Bootcamp Demo app, then:

```bash
PID=$(adb shell pidof com.bootcamp.demoapp | tr -d '\r')
echo $PID
adb shell "su -c 'timeout -s INT 20 strace -f -tt -s 96 -e trace=openat,faccessat,connect,execve -o /data/local/tmp/hand.txt -p $PID'"
```

While it runs (20 seconds), tap **1 Files**, **2 Network** and **8 Run a command** in the app. Then:

```bash
adb shell su -c "cat /data/local/tmp/hand.txt" | grep "com.bootcamp.demoapp"
adb shell su -c "cat /data/local/tmp/hand.txt" | grep "connect"
adb shell su -c "cat /data/local/tmp/hand.txt" | grep "execve"
```

**Questions (write the answers down):**
1. Which line shows `note.txt` being created? How can you tell it is being *written* and not just read?
2. Which `connect` line is the real internet connection? What address and port does it use?
3. How many `execve` lines are there for `getprop`, and why do most of them fail?

---

## Part B: Capture with Python (`strace_capture.py`)

Open `starter/strace_capture.py`. The skeleton (arguments, finding the emulator, pulling a file) is already written. You fill in four TODOs, **testing after each**.

### TODO 1: find the app's process id
Use `adb(serial, "shell", "pidof", package)`; it returns `(returncode, stdout, stderr)`. Return the text of stdout, or `""` if empty.

**Checkpoint 1** (app open on the emulator):
```bash
python3 -c "from strace_capture import *; print(find_pid(find_emulator(), 'com.bootcamp.demoapp'))"
```
Expected: a number such as `10350`.

### TODO 2: build the strace command from the config
Open `strace_config.json` and look at `categories`. Gather every syscall name into one list, then join the pieces:
```
strace -f -tt -s 128 -e trace=openat,unlinkat,...,execve,kill -o /data/local/tmp/lab4_strace.log -p 10350
```

**Checkpoint 2:**
```bash
python3 -c "
import json
from strace_capture import build_strace_command
print(build_strace_command(123, json.load(open('strace_config.json')), '/data/local/tmp/x.log'))"
```
Expected (one line): `strace -f -tt -s 128 -e trace=openat,unlinkat,mkdirat,renameat,faccessat,socket,connect,bind,execve,kill -o /data/local/tmp/x.log -p 123`

### TODO 3: run strace on the phone
Run `su -c 'timeout -s INT <seconds> <command>'` through `adb shell`. `su` makes it run as root (strace needs that), and `timeout -s INT` stops strace politely so the whole file is written.

### TODO 4: bring the log back
Read the remote file with `pull_text`, save it to `--out`, delete the remote file, and print the line count.

**Run it, and use the app while it traces:**
```bash
python3 strace_capture.py com.bootcamp.demoapp --duration 20 --out raw_strace.log
```
**Expected:**
```
[+] Using emulator-5554
[+] com.bootcamp.demoapp has process id 10350
[+] On the phone: strace -f -tt -s 128 -e trace=openat,...
[+] Tracing for 20 s. USE THE APP NOW (tap its buttons).
[+] 80 lines of raw strace output -> .../raw_strace.log
```
Open `raw_strace.log`. These are the lines you saw by hand in Part A.

---

## Part C: Turn text into records (`strace_parse.py`)

You can do this part with the sample log, no phone needed. Open `starter/strace_parse.py`.

### TODO 1 and 2: parse one line
`parse_line` receives one raw line. The regular expression `LINE` (already written) splits it into six pieces. Return a dict with `time`, `pid`, `syscall`, `category`, `target`, `args`, `result`, `error`, `ok`. `target_of` pulls out the *interesting* part: a path, an `address:port`, or a program.

**Checkpoint 3:**
```bash
python3 -c "
from strace_parse import *
cfg = load_config('strace_config.json'); cats = category_map(cfg)
print(parse_line('9764  17:14:15.980564 openat(AT_FDCWD, \"/data/user/0/com.bootcamp.demoapp/files/note.txt\", O_WRONLY|O_CREAT|O_TRUNC, 0600) = 55', cats))
print(parse_line('9911  17:14:19.240760 connect(65, {sa_family=AF_INET6, sin6_port=htons(443), inet_pton(AF_INET6, \"::ffff:172.66.147.243\", &sin6_addr), sin6_flowinfo=htonl(0), sin6_scope_id=0}, 28) = -1 EINPROGRESS (Operation now in progress)', cats))
print(parse_line('9566  17:12:52.294548 +++ exited with 0 +++', cats))"
```
Expected:
- 1st: `category: 'filesystem'`, `target: '/data/user/0/com.bootcamp.demoapp/files/note.txt'`, `result: '55'`, `ok: True`
- 2nd: `category: 'network'`, `target: '172.66.147.243:443'`, `error: 'EINPROGRESS'`, `ok: False`
- 3rd: `None` (it is not a call)

> `EINPROGRESS` is normal for a connection that is still starting. `ok: False` just means "result was -1".

### TODO 3 and 4: the summary
Print calls per category, then the number of failed calls and the 5 most common failures (`syscall -> error`).

### TODO 5: save JSON Lines
Write one `json.dumps(event)` per line to `--out`, as in Lab 3.

**Run it on the sample:**
```bash
python3 strace_parse.py ../solution/sample/strace_sample.log --out events.jsonl
```
**Expected (shortened):**
```
72 events -> .../events.jsonl

72 system calls recorded

== Calls by category ==
filesystem   57
network      10
process      5

== Failed calls: 15 ... ==
    8  faccessat -> ENOENT
    4  execve -> ENOENT
    ...

== app-private-storage (6)  ... ==
   /data/user/0/com.bootcamp.demoapp/files/note.txt
   /data/user/0/com.bootcamp.demoapp/shared_prefs/demo.xml
   ...
== internet-connection (1)  ... ==
   172.66.147.243:443   [failed: EINPROGRESS]
== program-start (5)  ... ==
   /system/bin/getprop
```

---

## Part D: End to end

1. Open the Bootcamp Demo app.
2. Capture while using the app: `python3 strace_capture.py com.bootcamp.demoapp --duration 30 --out raw_strace.log` (tap **Run ALL** and then each button).
3. Parse it: `python3 strace_parse.py raw_strace.log --out events.jsonl`
4. Open `events.jsonl`. Each line is one structured event, ready for a report.

**Make it your own (no code changes):** edit `strace_config.json`. Add `"unlinkat"` to a category you care about, or add a new highlight rule, then run again. This is the same idea as Lab 3's config file.

## Check yourself (these become report answers)

1. Why does `strace` need `su` (root) on the emulator?
2. Why do we pass `-e trace=...` instead of recording everything? (Hint: Demo 4, step 7.)
3. Which Java call matches `faccessat`? Which matches `execve`?
4. In the summary, why are there `ENOENT` failures for `getprop`, yet the program still ran?
5. What does strace show that a Frida hook on `URL` does not? What does Frida show that strace does not?

## Stuck?

| Problem | Try |
|---------|-----|
| `... is not running` | Open the app on the emulator first. |
| `Operation not permitted` / cannot attach | Another tool (Frida) is attached to the app. Stop it, then restart the app. |
| `0 lines` / nothing recorded | The app was idle. Tap its buttons **while** the capture runs. |
| `su: not found` | The emulator is not rooted; tell your instructor. |
| `NotImplementedError` | You have not filled in that TODO yet. |
| A call is missing from the summary | Is its name listed in `strace_config.json` under `categories`? |

## Extension (optional)

Add a highlight that flags any file opened under `/proc` or `/sys`, and list what the app reads there.

## How this helps the assignment

The assignment asks you to monitor native / system-level operations performed by the app and to record what you collect in a structured format. This lab gives you the whole pipeline in small pieces: a config that chooses which calls to watch, a script that runs `strace`, a parser that produces JSON Lines events, and a summary. For your submission, run it on the assignment app, keep `raw_strace.log` and `events.jsonl` as evidence, and describe what the system calls reveal.
