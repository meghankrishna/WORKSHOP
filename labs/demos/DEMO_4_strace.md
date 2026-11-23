# Demo 4 (Instructor): strace: watching what the app asks the operating system

**Time:** 20 minutes  **Supports:** Lab 4, assignment work on native / system-call monitoring
**Students should leave knowing:** every Java action ends as a *system call*; `strace` records those calls without any hooks, and it also sees things the app does outside Java (like starting another program).

## Before class

- Emulator running and **rooted** (`su` works). Check: `adb shell su -c id` prints `uid=0(root)`.
- strace is already on the emulator. Check: `adb shell su -c "strace -V"` prints `strace -- version 4.25`.
- **Bootcamp Demo** app installed (`demo-app/bootcamp-demo.apk`) and open on the emulator.
- Two terminals: one to run strace, one to look at results. The emulator window visible.
- Do **not** run Frida on the same app at the same time (two tools cannot both attach to one process).

## Steps

### 1. The idea, with a drawing  (3 min)

Draw on the board:
```
   Java code in the app           (Frida watches here)
          │
   Android framework
          │
   ──────────────────────────────────────────────
   system calls: openat, connect, execve ...      (strace watches here)
   ──────────────────────────────────────────────
          │
   Linux kernel: files, network, processes
```
**Say:** "An app cannot touch a file or the network by itself. It has to *ask the kernel*, using a **system call**. Think of the kernel as the front desk of a building: every request goes through it. `strace` stands at the front desk and writes down every request. No hooks, no code to write."

**Ask:** "Frida saw `FileOutputStream` being created. What do you think the kernel was asked?" (Take a guess, then show it in step 3.)

### 2. Attach strace to the app  (3 min)

In terminal 1, find the app's process id and start tracing. This one command traces file opens, file-exists checks, network connects and program starts, for 30 seconds:
```bash
PID=$(adb shell pidof com.bootcamp.demoapp | tr -d '\r')
echo $PID
adb shell "su -c 'timeout -s INT 30 strace -f -tt -s 96 -e trace=openat,faccessat,connect,execve -o /data/local/tmp/demo.txt -p $PID'"
```
Explain each flag in one line each:

| Flag | Meaning |
|------|---------|
| `-p $PID` | attach to the running app |
| `-f` | also follow its threads and any programs it starts |
| `-tt` | put a time on every line |
| `-s 96` | show up to 96 characters of each text argument |
| `-e trace=openat,faccessat,connect,execve` | only show these calls (otherwise thousands of lines per second) |
| `-o file` | write to a file on the phone instead of the screen |
| `timeout -s INT 30` | stop after 30 seconds so the file is finished properly |

**Say:** "Without `-e` the screen is a waterfall. Choosing *which* calls to watch is the main skill."

### 3. Files  (4 min)

While strace runs, in the app tap **1 Files**, then **5 Saved settings**, then **6 Database**. Wait for strace to finish, then in terminal 2:
```bash
adb shell su -c "cat /data/local/tmp/demo.txt" | grep "com.bootcamp.demoapp"
```
**Expect** lines like:
```
openat(AT_FDCWD, ".../files/note.txt", O_WRONLY|O_CREAT|O_TRUNC, 0600) = 55
openat(AT_FDCWD, ".../files/note.txt", O_RDONLY) = 55
openat(AT_FDCWD, ".../shared_prefs/demo.xml", O_RDONLY) = 65
openat(AT_FDCWD, ".../databases/demo.db", O_RDWR|O_CREAT|...) = 67
```
Also look at the "does this file exist?" checks that **1 Files** makes:
```bash
adb shell su -c "cat /data/local/tmp/demo.txt" | grep "faccessat" | grep -E "Download|hosts|does-not-exist"
```
```
faccessat(AT_FDCWD, "/sdcard/Download", F_OK) = 0
faccessat(AT_FDCWD, "/system/etc/hosts", F_OK) = 0
faccessat(AT_FDCWD, "/data/local/tmp/does-not-exist", F_OK) = -1 ENOENT (No such file or directory)
```
**Say:** "That is Java's `File.exists()`. `= 0` means yes, `ENOENT` means no. Malware checks for files this way, and now you can see every check."

**Point out:**
- `O_WRONLY|O_CREAT|O_TRUNC` means "create it, empty it, I will write": that is `new FileOutputStream(...)` from Java.
- `O_RDONLY` is `FileInputStream`.
- "Saved settings" is just a file, `shared_prefs/demo.xml`. "Database" is just a file, `demo.db`.
- The number after `=` is the **file descriptor**, the handle the kernel gives back. `-1` would mean it failed.

### 4. Network  (3 min)

Run strace again (same command) and tap **2 Network**. Then:
```bash
adb shell su -c "cat /data/local/tmp/demo.txt" | grep "connect"
```
**Expect:**
```
connect(55, {sa_family=AF_UNIX, sun_path="/dev/socket/dnsproxyd"}, 110) = 0
connect(55, {sa_family=AF_INET6, sin6_port=htons(443), inet_pton(AF_INET6, "::ffff:172.66.147.243", ...
```
**Point out:**
- First `connect` goes to `/dev/socket/dnsproxyd`: the app asking the system "what is the address of example.com?" (a DNS lookup).
- Second `connect` is the real connection: the address `172.66.147.243` on port `443` (HTTPS). The `::ffff:` in front is just how IPv6 writes an ordinary IPv4 address.
- It ends with `= -1 EINPROGRESS`. That is **normal**: the app asked for a connection without waiting ("non-blocking"), and the kernel says "working on it". It is not an error.
- **Say:** "Frida showed us the *name* `example.com`. strace shows the *address* the phone actually contacted. If an app hides the name, the address still gives it away."

### 5. Programs it starts: the thing Frida cannot see  (4 min)

Run strace again and tap **8 Run a command**. Then:
```bash
adb shell su -c "cat /data/local/tmp/demo.txt" | grep "execve"
```
**Expect:** several `execve("/sbin/getprop", ...) = -1 ENOENT`, then finally:
```
execve("/system/bin/getprop", ["getprop", "ro.product.model"], ...) = 0
```
**Point out:**
- `execve` = "start this program". The first tries fail (`ENOENT`, no such file) because the system searches several folders; the last one works (`= 0`).
- Because we used `-f`, strace also followed the new `getprop` process and recorded *its* activity (loading libraries, reading properties). That program runs outside the app's Java code.
- **Say:** "Frida hooked inside the app. strace sees what the app *causes*, even in other processes."

### 6. Side by side  (2 min)

Show this table; students have now seen both views of the same actions:

| The app did (Java) | Frida saw | strace saw |
|--------------------|-----------|------------|
| check a file exists | `File.exists()` | `faccessat("/data/.../x", F_OK)` (`ENOENT` = no) |
| write a file | `FileOutputStream.<init>` | `openat(... O_WRONLY\|O_CREAT ...)` |
| save a setting | `SharedPreferences ... putString` | `openat(".../shared_prefs/demo.xml")` |
| open a web page | `URL.<init>("https://example.com")` | `connect(... port 443, 172.66.147.243)` |
| run a command | `Runtime.exec("getprop", ...)` | `execve("/system/bin/getprop", ...)` |

**Say:** "Two tools, two levels. Next, in the lab, you write a small program that runs strace for you and turns the raw lines into a clean table."

### 7. Optional: the counts  (2 min)

A summary of *how many* of each call, for 8 seconds of normal app use (tap a button or two while it runs):
```bash
adb shell "su -c 'timeout -s INT 8 strace -f -c -p $PID'" 2>&1 | grep -v "attached\|detached"
```
**Expect** a table like `futex 346`, `epoll_pwait 3261`, `read 5994`, `write 1381`.
**Say:** "Thousands of calls in eight seconds, almost all of them background chatter. This is why we choose which calls to watch."

## Why this matters for the assignment

The assignment asks us to monitor native / system-level operations (system calls) and to store what we collect in a structured format. This demo shows the raw material; Lab 4 turns it into structured events with a small config and a parser.

## If it goes wrong

| Symptom | Fix |
|---------|-----|
| `su: not found` / permission denied | The emulator is not rooted. Run `./setup.sh verify` (it should say `Root: available`). |
| `strace: command not found` | Use the full path `/system/bin/strace`, or ask whether the image has it. |
| `strace: attach: ptrace(PTRACE_SEIZE...): Operation not permitted` | Another tool (Frida) is already attached to the app. Stop it, or restart the app. |
| Empty output file | The app made none of the chosen calls. Tap the buttons while strace is running, not before. |
| Output file is huge | Narrow `-e trace=...`, or shorten `timeout`. |
| The app feels slow or stops responding | Tracing slows an app down. Restart the app and trace again with a shorter `-e trace=` list. |
