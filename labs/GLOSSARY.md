# Glossary: words you will hear in this bootcamp

Plain-language meanings. You do not need to memorise these; come back whenever a word is unfamiliar.

| Word | What it means | Everyday comparison |
|------|---------------|---------------------|
| **Android emulator** | A fake Android phone running as a program on your laptop. | A flight simulator, but for phones. |
| **AVD** | "Android Virtual Device": the saved settings of one emulator (screen size, Android version). | The save file of your simulator. |
| **adb** | "Android Debug Bridge": a command-line tool on your laptop that talks to the phone/emulator. | A remote control for the phone. |
| **adb shell** | Opens a command line *inside* the phone. | Typing commands on the phone itself. |
| **Emulator console** | A control panel for the emulator itself (not for Android). Used to fake battery, GPS, network. Reached with `adb emu ...`. | The settings menu of the flight simulator, e.g. "make it rain". |
| **Package name** | The unique ID of an app, like `com.android.settings`. | An app's passport number. |
| **Dynamic analysis** | Studying an app by *running* it and watching what it does. | Watching a suspect instead of reading their diary. |
| **Static analysis** | Studying an app without running it. | Reading the diary. |
| **Frida** | A tool that injects your own code into a running app so you can watch (or change) what it does. | A tiny spy planted inside the app. |
| **frida-server** | The Frida helper program running *on the phone*. | The spy's radio. |
| **Hook** | Replacing a function in the app with your own version that records the call and then runs the original. | Putting a tap on a phone line: calls still go through, you just listen. |
| **Java API / method** | A built-in Android/Java function, like `File.exists()` ("does this file exist?"). | A button the app can press. |
| **Overload** | Several versions of the same method name with different inputs, e.g. `Log.d(tag, msg)` and `Log.d(tag, msg, error)`. | "Order pizza" by phone *or* by app: same action, different inputs. |
| **`$init`** | Frida's name for a *constructor* (the code that creates an object). | "Birth" of an object. |
| **Syscall** | A request from a program to the operating system's kernel: open a file, connect to the network. | Asking the front desk for something. |
| **strace** | A tool that records every system call a program makes. Needs root on the phone. | A security camera at the front desk. |
| **Root** | The all-powerful user on the phone. Some tools (strace, frida-server) only work as root. | The building manager's master key. |
| **File descriptor** | The small number the kernel hands back when you open a file or connection (the `= 55` after `openat`). | A cloakroom ticket number. |
| **JSON** | A text format for structured data: `{"name": "value"}`. | A neat form with labelled boxes. |
| **JSON Lines (JSONL)** | A file with **one JSON object per line**. Safe to write continuously. | A logbook where each line is one entry. |
| **Config file** | A file holding settings, so you change behaviour without editing code. | A settings page. |
| **Scenario** | A named set of emulator conditions, e.g. `low_battery`. | A test situation. |
| **Verify** | Read a value back to prove a change really happened. | Checking the door is locked after locking it. |
