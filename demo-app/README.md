# Bootcamp Demo App

A small, harmless Android app made for **instructor demonstrations**. Each button uses one kind of Android feature that our tools observe, so you can show an app *doing something* and then show the monitor *catching it*. A live panel at the top shows the battery, location and network the app sees, so changes from the emulator console are visible on screen.

- **Package:** `com.bootcamp.demoapp`  **File:** `bootcamp-demo.apk`  **Works on:** Android 6.0+ (tested on the `pixel-29` emulator)
- **Safe:** the only network call is one `GET https://example.com`. No data leaves the device.
- **Source:** `app/src/main/java/com/bootcamp/demoapp/MainActivity.java` (one file, about 400 lines, no extra libraries)

## What is on the screen

```
 Battery  : 100%  (on battery)        <- live: changes with `adb emu power ...`
 Location : 37.4220, -122.0840        <- live: changes with `adb emu geo fix ...`
 Network  : 1048576 kbps down         <- what Android reports
 Last GET : 283 ms                    <- how long the last request took
 [1 Files]          [2 Network]
 [3 Location]       [4 Phone info]
 [5 Saved settings] [6 Database]
 [7 Encryption]     [8 Run a command]
 [9 Installed apps] [Run ALL]
 [Clear log]
 (log of everything the app just did)
```

| Button | What the app does | Category the monitor files it under |
|--------|-------------------|-------------------------------------|
| 1 Files | checks 3 paths exist, writes then reads `note.txt` | filesystem |
| 2 Network | GET `https://example.com` and times it | network |
| 3 Location | asks for the last GPS fix and listens for updates | location |
| 4 Phone info | operator, SIM, phone number, device id (**device id is refused on purpose**), Android id | telephony, device_info |
| 5 Saved settings | saves and reads a fake token | shared_preferences |
| 6 Database | creates a table, inserts a row, counts rows | database |
| 7 Encryption | AES-encrypts a short message | crypto |
| 8 Run a command | runs `getprop ro.product.model` | process |
| 9 Installed apps | counts installed apps | package_info |
| Run ALL | all of the above, in order | everything |

Everything the app logs on screen is also written to the Android log: `adb logcat -s BootcampDemo`.

## Install and open

```bash
adb install -r demo-app/bootcamp-demo.apk
adb shell pm grant com.bootcamp.demoapp android.permission.ACCESS_FINE_LOCATION
adb shell pm grant com.bootcamp.demoapp android.permission.READ_PHONE_STATE
adb shell monkey -p com.bootcamp.demoapp -c android.intent.category.LAUNCHER 1
```
(The two `pm grant` lines skip the permission pop-ups. You can also just tap Allow.)

## Demo A: what an app does (no tools)

1. Tap **Run ALL**. The log shows every action; the numbers in `Last GET` and the status panel fill in.
2. Tap **4 Phone info** and point at the `getDeviceId refused (SecurityException)` line: "apps are not always allowed to ask for everything."

## Demo B: change the phone's world, watch the app react (Demo 2 / Lab 2)

```bash
# Battery: the panel changes within a couple of seconds
adb emu power capacity 5
adb emu power ac off
#   If the panel does not move (the console changes the virtual hardware but Android
#   sometimes stops noticing), use the override. It always works and is instant:
adb shell dumpsys battery set level 5
adb shell dumpsys battery unplug
#   undo it with:  adb shell dumpsys battery reset

# Location: the log prints "location: moved to ..." and the panel updates
adb emu geo fix 78.4867 17.385          # Hyderabad (longitude FIRST)
adb emu geo fix 139.6917 35.6895        # Tokyo

# No network: tap "2 Network" and watch it fail, then restore
adb shell svc wifi disable; adb shell svc data disable
#   -> log: network: java.net.UnknownHostException: Unable to resolve host "example.com"
adb shell svc wifi enable;  adb shell svc data enable
```
Reset afterwards: `adb emu power ac on`, `adb emu power capacity 100`, and re-enable Wi-Fi and data.

> **Network speed is not a reliable demo on this emulator.** `adb emu network speed edge` is accepted (`adb emu network status` shows 7 KB/s) but requests still finish in about 45 ms and the app's reported bandwidth does not change. Use the Wi-Fi off/on switch above to show a network condition; it is clear and repeatable. (This matches the `confirmed=False` network results in the earlier saved run.)

## Demo C: catch it with Frida (Demo 3 / Lab 3 / the assignment framework)

`demo_apis.json` lists 25 APIs in 10 categories matching this app. Start the monitor, then use the app (the framework starts the app itself; press Ctrl+C when done):

```bash
source venv/bin/activate
python3 api_monitor.py com.bootcamp.demoapp --config demo-app/demo_apis.json
```
While it runs, tap **Run ALL**, switch Wi-Fi off and tap **2 Network**, and change the location. Results are written to `Output/api_monitor_logs.jsonl`, one JSON record per call.

For the small step-by-step version used in the lab (two APIs from a config file):
```bash
cd labs/lab3_frida_first_hooks
python3 run_frida.py com.bootcamp.demoapp solution/step4_config_driven.js --config apis_demo.json --duration 30
```

**What a good run looks like** (measured on the `pixel-29` emulator with `api_monitor.py`, one Run ALL plus a network failure plus a location change): about 80 records covering all 10 categories: filesystem, device_info, network, telephony, location, shared_preferences, database, crypto, process and package_info.

Nice records to put on screen:

| Category | What the monitor captured |
|----------|---------------------------|
| network | `URL.<init>("https://example.com")` |
| location | `getLastKnownLocation("gps")` returning the position you set with `geo fix` |
| shared_preferences | `getString("token", "none")` returning `"abc123-demo-token"` |
| crypto | `Cipher.doFinal` with the plaintext bytes in and ciphertext bytes out |
| process | `Runtime.exec("getprop", "ro.product.model")` |
| exceptions | the refused `getDeviceId`, and `UnknownHostException` while the network is off |

## Demo D: the same app at the system-call level (Demo 4 / Lab 4)

`strace` is already on the emulator and runs as root. Open the app, then trace it for 30 seconds while you tap its buttons (do not run Frida on the app at the same time):

```bash
PID=$(adb shell pidof com.bootcamp.demoapp | tr -d '\r')
adb shell "su -c 'timeout -s INT 30 strace -f -tt -s 96 -e trace=openat,faccessat,connect,execve -o /data/local/tmp/demo.txt -p $PID'"
adb shell su -c "cat /data/local/tmp/demo.txt" | grep -E "com.bootcamp.demoapp|connect|execve|faccessat"
```

What each button looks like to the kernel (measured on the `pixel-29` emulator):

| Button | System calls strace records |
|--------|-----------------------------|
| 1 Files | `faccessat(".../does-not-exist", F_OK) = -1 ENOENT`; `openat(".../files/note.txt", O_WRONLY\|O_CREAT\|O_TRUNC) = 55`, then `O_RDONLY` |
| 2 Network | `connect(... "/dev/socket/dnsproxyd")` (name lookup), then `connect(... "172.66.147.243", port 443) = -1 EINPROGRESS` (normal: non-blocking) |
| 5 Saved settings | `openat(".../shared_prefs/demo.xml", O_RDONLY)` |
| 6 Database | `openat(".../databases/demo.db", O_RDWR\|O_CREAT ...)` and `demo.db-journal` |
| 8 Run a command | four failed `execve(... "getprop") = -1 ENOENT` then `execve("/system/bin/getprop") = 0` |

Full script: `labs/demos/DEMO_4_strace.md`. Students build the capture-and-parse tools in `labs/lab4_strace/`.

## Rebuilding the app (instructor only)

Needs Java 17 and the Android SDK (platform 35). From this folder:
```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@17 ANDROID_HOME=$HOME/Android/Sdk
echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew :app:assembleDebug
# result: app/build/outputs/apk/debug/app-debug.apk
```
