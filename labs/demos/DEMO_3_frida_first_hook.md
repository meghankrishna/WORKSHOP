# Demo 3 (Instructor): Your first hook: watching an app from the inside

**Time:** 20 minutes  **Supports:** Lab 3, Assignment Task 3
**Students should leave knowing:** a hook is a tap on a function: the app still works, we just see every call.
In this demo we only *observe*. We never change what the app receives.

## Before class

- Emulator running, frida-server running, `adb forward tcp:27042 tcp:27042` done.
- Target app **already open** on the emulator: the **Bootcamp Demo** app (`demo-app/bootcamp-demo.apk`). Frida attaches to the running app. (The built-in Settings app is too quiet: it triggers almost none of these calls.)
- `labs/lab3_frida_first_hooks/solution/` open in a terminal. Use `solution/step1_hello.js` etc.

## Steps

### 1. The idea, with a drawing  (3 min)

Draw on the board:
```
 App code  ──calls──▶  File.exists("/sdcard/x")  ──▶  answer
                              ▲
                        our hook sits here:
                        "write down the call, then pass it on"
```
**Say:** "The app has no idea. We write down each call and then let the real function run."

### 2. Hook one function  (5 min)

Show `solution/step1_hello.js` on screen (it is 8 lines; read it aloud).
**Run:**
```bash
python3 run_frida.py com.bootcamp.demoapp solution/step1_hello.js --duration 20
```
**Do:** tap **1 Files** and **Run ALL** in the app.
**Expect:** lines like `File.exists() was called` scrolling by.
**Say:** "Every line is the app asking *does this file exist?* We never knew it asked so often."

### 3. Show the details: arguments and answers  (5 min)

**Run** `solution/step2_args_and_result.js` the same way.
**Expect:** `File.exists("/data/user/0/...") -> true`
**Point out:** now we see *what* was asked (the argument) and *what the answer was* (the return value). "That is what the assignment calls arguments and return value."

### 4. Overloads  (4 min)

Open `solution/step3_overloads.js`.
**Say:** "`Log.d` exists in two versions: with and without an error. Same name, different inputs. Those are *overloads*. We hook all of them with a loop."
**Run** it and point at the two `hooking Log.d(...)` lines it prints first.

### 5. Preview of the assignment  (3 min)

**Say:** "Typing a new hook for every function does not scale. Next demo: one program that reads the list from a file."

## Why this matters for the assignment

Task 3 *is* this, generalised. Steps 1 to 3 give students the three building blocks (hook, log arguments and return value, handle overloads). Step 4 adds the config file. The assignment extends it to full records (timestamp, class, method, arguments, return value, exception) saved as JSON Lines.

## If it goes wrong

| Symptom | Fix |
|---------|-----|
| `... is not running` | The app is not open. Open it, then check it is listed by `frida-ps -Ua` (package name in the **Identifier** column). |
| `Failed to attach` / connection error | frida-server not running, or versions of Frida host and server differ. |
| No output at all | The app is idle. Tap around; some functions simply are not called often. |
| Output floods the screen | Use `--duration 10`, or hook a rarer function. |
