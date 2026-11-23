// environment_hooks.js -- Task 2 (emulator-detection mitigation)

var DEFAULT_PROFILE = {
  build: {
    FINGERPRINT:
      "google/marlin/marlin:10/QP1A.191005.007.A3/5972272:user/release-keys",
    MODEL: "Pixel XL",
    MANUFACTURER: "Google",
    BRAND: "google",
    PRODUCT: "marlin",
    DEVICE: "marlin",
    HARDWARE: "marlin",
    BOOTLOADER: "marlin-10.34",
    BOARD: "marlin",
    SERIAL: "FA6AY0305718",
  },

  systemProps: {
    "ro.kernel.qemu": "0",
    "ro.boot.qemu": null,
    "ro.hardware": "marlin",
    "ro.hardware.chipname": "msm8996",
    "ro.product.device": "marlin",
    "ro.product.model": "Pixel XL",
    "ro.product.manufacturer": "Google",
    "ro.build.characteristics": "nosdcard",
    "ro.build.tags": "release-keys",
    "ro.bootloader": "marlin-10.34",
    "ro.boot.hardware": "marlin",
    "init.svc.qemud": null,
    "init.svc.qemu-props": null,
    "qemu.hw.mainkeys": null,
    "qemu.sf.fake_camera": null,
    "qemu.sf.lcd_density": null,
    "ro.kernel.android.qemud": null,
  },

  blacklistedPaths: [
    "/dev/qemu_pipe",
    "/dev/socket/qemud",
    "/dev/socket/genyd",
    "/dev/socket/baseband_genyd",
    "/system/lib/libc_malloc_debug_qemu.so",
    "/system/lib64/libc_malloc_debug_qemu.so",
    "/sys/qemu_trace",
    "/system/bin/qemu-props",
    "/system/bin/qemud",
    "dev/qemu_pipe",
    "dev/socket/qemud",
    "dev/socket/genyd",
    "dev/socket/baseband_genyd",
    "system/lib/libc_malloc_debug_qemu.so",
    "system/lib64/libc_malloc_debug_qemu.so",
    "sys/qemu_trace",
    "system/bin/qemu-props",
    "system/bin/qemud",
    "/system/bin/ldinit",
    "/system/bin/ldmountsf",
    "/system/bin/bstsvcmgrtest",
    "/system/bin/bstshutdown",
    "/system/bin/bstsyncfs",
    "/system/bin/bstime",
    "/system/bin/bstfolder",
    "/system/bin/bstshutdown_core",
    "/boot/bstmods/bstpgaipc.ko",
    "/boot/bstmods/bstaudio.ko",
    "/boot/bstmods/bstcamera.ko",
    "/boot/bstmods/bstvmsg.ko",
    "/boot/bstmods/bstinput.ko",
    "/boot/bstsetup.env",
    "/boot/bin/bstreport",
    "/boot/bin/bstconf",
    "/boot/bstsetconf.sh",
    "/system/bin/nox-prop",
    "/system/bin/nox-vbox-sf",
    "/system/bin/noxd",
    "/system/lib/libnoxd.so",
    "/system/lib/libnoxspeedup.so",
    "/system/lib/libhoudini.so",
    "/system/lib64/libhoudini.so",
  ],

  blacklistedPackages: [
    "com.google.android.launcher.layouts.genymotion",
    "com.bluestacks",
    "com.bignox.app",
    "com.vphone.launcher",
  ],

  telephony: {
    deviceId: null,
    imei: null,
    line1Number: null,
    subscriberId: null,
    networkOperatorName: "RJIO",
    simOperatorName: "RJIO",
  },

  androidId: null,

  features: {
    "android.hardware.sensor.accelerometer": true,
    "android.hardware.sensor.gyroscope": true,
    "android.hardware.sensor.light": true,
    "android.hardware.sensor.proximity": true,
    "android.hardware.sensor.compass": true,
    "android.hardware.camera": true,
    "android.hardware.camera.front": true,
    "android.hardware.bluetooth": true,
    "android.hardware.telephony": true,
    "android.hardware.telephony.gsm": true,
    "android.hardware.wifi": true,
    "android.hardware.nfc": false,
  },

  // -------------------------------------------------------------------------
  // NATIVE LAYER SWITCHES  (default OFF -- see the EGL note at the top)
  // -------------------------------------------------------------------------
  // Wrapping hot libc functions (open/openat/close/access/stat) and syscall()
  // in Frida callbacks perturbs the emulator's timing-sensitive EGL handshake
  // on the RenderThread, which fails as EGL_NOT_INITIALIZED and aborts the app.
  // DIVA's emulator-detection checks are all Java-level, so the Java layer alone
  // (Build + SystemProperties + File.exists + Telephony) fully satisfies Task 2.
  //
  // If you want native-level mitigation anyway (e.g. to also catch a native
  // detector lib for the report), set nativeFileHooks:true. It will then be
  // installed LAZILY -- only after the first Activity resumes -- so EGL has
  // already initialised and the hot hooks can no longer break graphics init.
  nativeFileHooks: false,

  // syscall() observer for exit/exit_group/tgkill from the detector. Pure
  // logging, but syscall() is hot enough to perturb EGL, so it is also gated
  // and installed lazily. Off by default; not needed for DIVA.
  nativeSyscallObserver: false,

  // Native OBSERVERS: the dlopen/android_dlopen_ext watcher (used to inspect a
  // native detector lib) and the abort/exit/kill loggers. These are pure
  // Interceptor.attach on native libc, and ANY native attach installed before
  // EGL initialises breaks the RenderThread (the emulator loads its EGL driver
  // through dlopen). Off by default so the app launches cleanly with Java-only
  // mitigation; when on, they are installed LAZILY after the first frame.
  nativeObservers: false,

  // set VERBOSE:true in DEVICE_PROFILE if you want every allowed File.exists /
  // native open logged. off by default because DIVA startup spams hundreds of
  // them across threads and it drowns out the actual detection hits.
  verbose: false,
};

/* eslint-disable no-undef */
var PROFILE =
  typeof DEVICE_PROFILE !== "undefined" ? DEVICE_PROFILE : DEFAULT_PROFILE;
/* eslint-enable no-undef */

var VERBOSE = !!PROFILE.verbose;
var NATIVE_FILE_HOOKS =
  PROFILE.nativeFileHooks === undefined ? false : !!PROFILE.nativeFileHooks;
var NATIVE_SYSCALL_OBSERVER =
  PROFILE.nativeSyscallObserver === undefined
    ? false
    : !!PROFILE.nativeSyscallObserver;
var NATIVE_OBSERVERS =
  PROFILE.nativeObservers === undefined ? false : !!PROFILE.nativeObservers;
var ANY_NATIVE =
  NATIVE_FILE_HOOKS || NATIVE_SYSCALL_OBSERVER || NATIVE_OBSERVERS;

/* ==========================================================================
 * 2. SMALL HELPERS
 * ========================================================================== */

function log(tag, msg) {
  console.log("[environment_hooks][" + tag + "] " + msg);
}

function vlog(tag, msg) {
  if (VERBOSE) log(tag, msg);
}

function randomDigits(n) {
  var s = "";
  for (var i = 0; i < n; i++) s += Math.floor(Math.random() * 10);
  return s;
}

function randomAndroidId() {
  var hex = "0123456789abcdef";
  var s = "";
  for (var i = 0; i < 16; i++) s += hex.charAt(Math.floor(Math.random() * 16));
  return s;
}

function luhnCheckDigit(partial) {
  var sum = 0;
  var alt = true; // check digit position is even (0-indexed from the right)
  for (var i = partial.length - 1; i >= 0; i--) {
    var n = parseInt(partial.charAt(i), 10);
    if (alt) {
      n *= 2;
      if (n > 9) n -= 9;
    }
    sum += n;
    alt = !alt;
  }
  return (10 - (sum % 10)) % 10;
}

function generateImei() {
  var tac = "35" + randomDigits(6); // plausible Type Allocation Code prefix
  var snr = randomDigits(6);
  var partial = tac + snr; // 14 digits
  return partial + luhnCheckDigit(partial);
}

function randomMsisdn() {
  return "1555" + randomDigits(7);
}

function isBlacklisted(path, blacklist) {
  for (var i = 0; i < blacklist.length; i++) {
    if (path.indexOf(blacklist[i]) !== -1) return true;
  }
  return false;
}

// Hooks a method overload only if it exists on this API level/OEM build;
// logs and continues instead of throwing if it does not.
function safeOverload(clazz, methodName, argTypes, impl) {
  try {
    var method = clazz[methodName];
    if (!method) return;
    var overload = argTypes.length
      ? method.overload.apply(method, argTypes)
      : method.overload();
    overload.implementation = impl;
  } catch (e) {
    log(methodName, "overload(" + argTypes.join(",") + ") not available: " + e);
  }
}

// Which module made this native call. Used everywhere below to tell "the app /
// the detector is probing" apart from "the framework/graphics stack is just
// doing its job". Getting this wrong is how you break EGL.
function callerModuleName(returnAddress) {
  try {
    var m = Process.findModuleByAddress(returnAddress);
    return m ? m.name : null;
  } catch (e) {
    return null;
  }
}

// heuristics for "this call came from the app/detector, not from system libs"
var APP_HINTS = [
  "libemulatordetector.so",
  "/data/app/",
  "/data/data/",
  "base.apk",
  "base.odex",
  "/oat/", // the app's compiled dex lands under .../oat/...
];

function isAppCaller(returnAddress) {
  var name = callerModuleName(returnAddress);
  if (!name) return false;
  for (var i = 0; i < APP_HINTS.length; i++) {
    if (name.indexOf(APP_HINTS[i]) !== -1) return true;
  }
  return false;
}

var SELF_TERMINATION_TARGETS = ["libemulatordetector.so", "base.apk"];

function isTargetCaller(returnAddress) {
  var name = callerModuleName(returnAddress);
  if (!name) return false;
  return SELF_TERMINATION_TARGETS.some(function (n) {
    return name.indexOf(n) !== -1;
  });
}

/* ==========================================================================
 * 2b. GRAPHICS-SAFE NATIVE DECISION  (the core of the crash fix)
 * ==========================================================================
 * These paths are load-bearing for the emulated GPU / HAL / dynamic linker.
 * If we block, EPERM, or redirect ANY of them, eglInitialize() fails and the
 * RenderThread aborts with EGL_NOT_INITIALIZED -- which is exactly the crash
 * we were seeing. The rule: the native layer must never touch them for a
 * system/graphics caller. */
function graphicsCritical(path) {
  if (!path) return false;
  return (
    path.indexOf("/dev/") === 0 || // ALL device nodes: qemu_pipe, goldfish_pipe, dri, socket, ...
    path.indexOf("/apex/") === 0 || // runtime/linker apex libs
    path.indexOf("/vendor/lib") !== -1 || // vendor HAL .so's (gralloc/egl/hwcomposer)
    path.indexOf("qemu_pipe") !== -1 ||
    path.indexOf("goldfish_pipe") !== -1 ||
    path.indexOf("gralloc") !== -1 ||
    path.indexOf("hwcomposer") !== -1 ||
    path.indexOf("/dri") !== -1 ||
    path.indexOf("gpu") !== -1 ||
    path.indexOf("egl") !== -1 ||
    path.indexOf("EGL") !== -1 ||
    path.indexOf("GLES") !== -1
  );
}

// Single decision function shared by the probe and open layers.
// Returns "block" or "pass". (Redirects are decided separately, below.)
//
//   - Only ever act on a blacklisted (qemu/geny/nox/bstacks) path.
//   - Never act for a system/graphics caller  -> EGL, RIL, sensors stay alive.
//   - Device nodes are only blocked when the request specifically came from
//     the detector library (libemulatordetector.so), never from anyone else,
//     so the RenderThread's /dev/qemu_pipe access always succeeds.
//   - Non-device blacklisted paths (qemud binary, libhoudini.so, bstacks...)
//     may be blocked for the app or the detector -- these are inert w.r.t.
//     graphics.
function decideNative(path, returnAddress, blacklist) {
  if (!path) return "pass";
  if (!isBlacklisted(path, blacklist)) return "pass";

  var fromDetector = isTargetCaller(returnAddress);
  var fromApp = isAppCaller(returnAddress);

  if (!fromDetector && !fromApp) return "pass"; // system / graphics -> hands off

  if (graphicsCritical(path)) {
    // device node etc.: only the detector lib gets a fake answer; everyone
    // else (incl. the graphics stack) is left completely alone.
    return fromDetector ? "block" : "pass";
  }

  return "block"; // safe, non-graphics blacklisted path from app/detector
}

/* ==========================================================================
 * 3. HOOK IMPLEMENTATIONS
 * ========================================================================== */

// --- Category 1: Android Build information --------------------------------
function hookBuildInfo() {
  try {
    var Build = Java.use("android.os.Build");
    var fields = PROFILE.build;
    Object.keys(fields).forEach(function (key) {
      try {
        if (Build[key] && fields[key] !== null && fields[key] !== undefined) {
          var original = Build[key].value;
          Build[key].value = fields[key];
          log("Build", key + ': "' + original + '" -> "' + fields[key] + '"');
        }
      } catch (e) {
        log("Build", "could not set field " + key + ": " + e);
      }
    });
  } catch (e) {
    log("Build", "hookBuildInfo failed: " + e);
  }
}

// --- Category 2: Android system properties ---------------------------------
// NOTE: this hooks the *Java* android.os.SystemProperties.get only. The native
// graphics stack reads properties through __system_property_get (not hooked),
// so spoofing ro.hardware here can never misdirect the native EGL/gralloc
// driver selection -- another reason the graphics stack is unaffected.
function hookSystemProperties() {
  try {
    var SystemProperties = Java.use("android.os.SystemProperties");
    var propMap = PROFILE.systemProps;

    safeOverload(SystemProperties, "get", ["java.lang.String"], function (key) {
      if (Object.prototype.hasOwnProperty.call(propMap, key)) {
        var spoofed = propMap[key];
        var original = this.get(key);
        log(
          "SystemProperties",
          'get("' +
            key +
            '"): "' +
            original +
            '" -> "' +
            (spoofed === null ? "" : spoofed) +
            '"',
        );
        return spoofed === null ? "" : spoofed;
      }
      return this.get(key);
    });

    safeOverload(
      SystemProperties,
      "get",
      ["java.lang.String", "java.lang.String"],
      function (key, def) {
        if (Object.prototype.hasOwnProperty.call(propMap, key)) {
          var spoofed = propMap[key];
          log(
            "SystemProperties",
            'get("' +
              key +
              '", def="' +
              def +
              '") -> "' +
              (spoofed === null ? def : spoofed) +
              '"',
          );
          return spoofed === null ? def : spoofed;
        }
        return this.get(key, def);
      },
    );
  } catch (e) {
    log("SystemProperties", "hookSystemProperties failed: " + e);
  }
}

// fd -> path, but ONLY for the handful of interesting files. keeping this map
// tiny matters: it used to hold every open fd in the process and got checked on
// every read(), which was pointless overhead.
var fdPathMap = {};

// real /proc file -> our sanitized copy in the app's data dir. filled in by
// prepareSanitizedProc(); used to redirect app opens away from the goldfish
// giveaway without touching a single byte in flight.
var procRedirects = {};

// Memory.allocUtf8String buffers we hand to native code as replacement paths.
// have to keep a reference or the GC frees them out from under the syscall.
var keepAlivePaths = [];

var INTERESTING_PATH_HINTS = [
  "cpuinfo",
  "/proc/tty",
  "qemu",
  "genymotion",
  "geny",
  "nox",
  "vbox",
  "bluestacks",
  "andy",
  "ttVM",
  "x86.prop",
  "goldfish",
  "ranchu",
  "/dev/socket/",
  "egl/lib",
];

function isInterestingPath(path) {
  if (!path) return false;
  for (var i = 0; i < INTERESTING_PATH_HINTS.length; i++) {
    if (path.indexOf(INTERESTING_PATH_HINTS[i]) !== -1) return true;
  }
  return false;
}

// Read a file through Java (so it works as the app uid and picks up SELinux
// context correctly). Returns null on any failure.
function slurpJava(path) {
  try {
    var FileReader = Java.use("java.io.FileReader");
    var BufferedReader = Java.use("java.io.BufferedReader");
    var StringBuilder = Java.use("java.lang.StringBuilder");
    var br = BufferedReader.$new(FileReader.$new(path));
    var sb = StringBuilder.$new();
    var line;
    while ((line = br.readLine()) !== null) {
      sb.append(line).append("\n");
    }
    br.close();
    return sb.toString();
  } catch (e) {
    return null;
  }
}

function spitJava(path, content) {
  try {
    var FileWriter = Java.use("java.io.FileWriter");
    var fw = FileWriter.$new(path);
    fw.write(content);
    fw.close();
    return true;
  } catch (e) {
    log("proc-redirect", "could not write " + path + ": " + e);
    return false;
  }
}

function appFilesDir() {
  try {
    var ActivityThread = Java.use("android.app.ActivityThread");
    var app = ActivityThread.currentApplication();
    if (!app) return null;
    return app.getApplicationContext().getFilesDir().getAbsolutePath();
  } catch (e) {
    return null;
  }
}

// Instead of rewriting /proc/cpuinfo bytes on every read() (which is a hot-path
// hook AND easy to corrupt), we make ONE clean copy up front and just redirect
// the app's open() to it. Same result, no per-read cost, no buffer surgery.
// NB: /proc/cpuinfo and /proc/tty/drivers are NOT graphicsCritical, so
// redirecting them for app callers is safe.
function prepareSanitizedProc() {
  var dir = appFilesDir();
  if (!dir) {
    log("proc-redirect", "no app files dir yet, skipping /proc sanitisation");
    return;
  }

  var jobs = [
    { src: "/proc/cpuinfo", out: dir + "/.san_cpuinfo" },
    { src: "/proc/tty/drivers", out: dir + "/.san_tty_drivers" },
  ];

  jobs.forEach(function (job) {
    var text = slurpJava(job.src);
    if (text === null) return;

    // goldfish/ranchu are the dead giveaways. swap them for something boring;
    // for the tty list just drop the goldfish console line entirely.
    var cleaned;
    if (job.src.indexOf("tty") !== -1) {
      cleaned = text
        .split("\n")
        .filter(function (l) {
          return l.indexOf("goldfish") === -1;
        })
        .join("\n");
    } else {
      cleaned = text
        .split("goldfish")
        .join("keystone")
        .split("ranchu")
        .join("keystone");
    }

    if (spitJava(job.out, cleaned)) {
      procRedirects[job.src] = job.out;
      log("proc-redirect", job.src + " -> " + job.out);
    }
  });
}

// Java layer: File.exists() is a pure probe, safe to lie to freely. This is
// where DIVA / the emulator-detector library actually test for /dev/qemu_pipe,
// /system/bin/qemud, etc. Lying here mitigates those checks WITHOUT touching
// the native device nodes the graphics stack needs -- and it never perturbs
// EGL, so it is always installed, at startup.
function hookFileExistsJava() {
  var blacklist = PROFILE.blacklistedPaths;
  try {
    var FileCls = Java.use("java.io.File");

    FileCls.exists.implementation = function () {
      var path = this.getAbsolutePath();
      vlog("File", 'exists("' + path + '") CALLED');

      if (isBlacklisted(path, blacklist)) {
        log("File", 'BLOCKED "' + path + '"');
        return false;
      }
      return this.exists();
    };

    log("File", "java.io.File.exists hooked");
  } catch (e) {
    log("File", "Java hook failed: " + e);
  }
}

// The native libc file layer. Installed LAZILY (see scheduleNativeAfterUI) so
// that EGL has finished initialising before we wrap any hot libc function.
function installNativeFileHooks() {
  var blacklist = PROFILE.blacklistedPaths;

  // build the sanitized /proc copies BEFORE we install the native open hooks,
  // so our own reads of the real files don't get redirected mid-setup.
  prepareSanitizedProc();

  // --- native layer ---------------------------------------------------------
  // PROBE syscalls (access/stat) only ask "does this exist / can I reach it".
  // OPEN syscalls do REAL work -- the goldfish EGL driver and gralloc open pipe
  // devices through these same libc entry points. Both layers now route every
  // decision through decideNative(), which refuses to touch graphics-critical
  // paths for system callers. That is what keeps EGL alive.
  var PROBE_SYMBOLS = [
    "access",
    "faccessat",
    "stat",
    "lstat",
    "stat64",
    "lstat64",
  ];
  var OPEN_SYMBOLS = ["open", "openat", "fopen"];

  var libc;
  try {
    libc = Process.getModuleByName("libc.so");
  } catch (e) {
    log("native", "libc.so unavailable: " + e);
    return;
  }

  function pathArgIndexFor(symbol) {
    // openat / faccessat are (dirfd, path, ...), everything else is (path, ...)
    return symbol === "openat" || symbol === "faccessat" ? 1 : 0;
  }

  // probes: block ONLY per decideNative() (blacklisted + app/detector caller,
  // graphics-safe). System/graphics callers always pass through untouched.
  PROBE_SYMBOLS.forEach(function (symbol) {
    try {
      var addr = libc.findExportByName(symbol);
      if (addr === null) {
        vlog("native:" + symbol, "NOT FOUND");
        return;
      }
      var idx = pathArgIndexFor(symbol);

      Interceptor.attach(addr, {
        onEnter: function (args) {
          try {
            this.path = args[idx].readUtf8String();
          } catch (e) {
            this.path = null;
          }
          this.act = decideNative(this.path, this.returnAddress, blacklist);
        },
        onLeave: function (retval) {
          if (this.act === "block") {
            log(
              "native:" + symbol,
              "BLOCKED " +
                this.path +
                " (caller=" +
                (callerModuleName(this.returnAddress) || "?") +
                ")",
            );
            retval.replace(ptr("-1")); // access/stat: -1 == "no such file"
          }
        },
      });

      log("native:" + symbol, "HOOK INSTALLED (probe, graphics-safe)");
    } catch (e) {
      log("native:" + symbol, "HOOK ERROR: " + e);
    }
  });

  // opens: same graphics-safe blocking decision, plus /proc redirect for app
  // callers only (and never for graphics-critical paths).
  OPEN_SYMBOLS.forEach(function (symbol) {
    try {
      var addr = libc.findExportByName(symbol);
      if (addr === null) {
        vlog("native:" + symbol, "NOT FOUND");
        return;
      }
      var idx = pathArgIndexFor(symbol);

      Interceptor.attach(addr, {
        onEnter: function (args) {
          try {
            this.path = args[idx].readUtf8String();
          } catch (e) {
            this.path = null;
          }

          this.idx = idx;
          this.interesting = isInterestingPath(this.path);
          if (this.interesting) {
            vlog("native:" + symbol, "CALLED " + (this.path || "<unknown>"));
          }

          this.act = decideNative(this.path, this.returnAddress, blacklist);

          // /proc redirect: only for app/detector callers, only for the
          // non-graphics /proc files we sanitised, and never if we're blocking.
          if (
            this.act !== "block" &&
            this.path &&
            !graphicsCritical(this.path) &&
            (isAppCaller(this.returnAddress) ||
              isTargetCaller(this.returnAddress)) &&
            Object.prototype.hasOwnProperty.call(procRedirects, this.path)
          ) {
            var repl = Memory.allocUtf8String(procRedirects[this.path]);
            keepAlivePaths.push(repl);
            args[this.idx] = repl;
            log(
              "native:" + symbol,
              "REDIRECT " + this.path + " -> " + procRedirects[this.path],
            );
          }
        },

        onLeave: function (retval) {
          if (this.act === "block") {
            log(
              "native:" + symbol,
              "BLOCKED " +
                this.path +
                " (caller=" +
                (callerModuleName(this.returnAddress) || "?") +
                ")",
            );
            retval.replace(symbol === "fopen" ? ptr("0") : ptr("-1"));
            return;
          }

          // remember interesting fds only, for nicer logging elsewhere
          if ((symbol === "open" || symbol === "openat") && this.interesting) {
            var fd = retval.toInt32();
            if (this.path && fd >= 0) {
              fdPathMap[fd] = this.path;
              vlog("native:" + symbol, "tracked fd " + fd + " -> " + this.path);
            }
          }
        },
      });

      log("native:" + symbol, "HOOK INSTALLED (open, graphics-safe)");
    } catch (e) {
      log("native:" + symbol, "HOOK ERROR: " + e);
    }
  });

  // keep fdPathMap from leaking as fds get recycled
  try {
    var closeAddr = libc.findExportByName("close");
    if (closeAddr) {
      Interceptor.attach(closeAddr, {
        onEnter: function (args) {
          this.fd = args[0].toInt32();
        },
        onLeave: function (retval) {
          if (Object.prototype.hasOwnProperty.call(fdPathMap, this.fd)) {
            delete fdPathMap[this.fd];
          }
        },
      });
      log("native:close", "HOOK INSTALLED (fdPathMap cleanup)");
    }
  } catch (e) {
    log("native:close", "HOOK ERROR: " + e);
  }
}

function inspectEmulatorDetector(m) {
  console.log("\n=== " + m.name + " ===");
  console.log("Module: " + m.name);
  console.log("Base:   " + m.base);
  console.log("Size:   " + m.size);

  m.enumerateExports().forEach(function (e) {
    if (e.type === "function") {
      console.log(e.address + " " + e.name);
    }
  });
}

function hookLibraryLoad() {
  try {
    var libc = Process.getModuleByName("libc.so");
    ["android_dlopen_ext", "dlopen"].forEach(function (sym) {
      var addr = libc.findExportByName(sym);
      if (!addr) return;

      Interceptor.attach(addr, {
        onEnter: function (args) {
          try {
            this.path = args[0].readUtf8String();
          } catch (e) {
            this.path = null;
          }
        },
        onLeave: function (retval) {
          if (this.path && this.path.indexOf("libemulatordetector.so") !== -1) {
            setTimeout(function () {
              var m = Process.findModuleByName("libemulatordetector.so");
              if (!m) return;
              inspectEmulatorDetector(m);
              hookSuspiciousExports(m);
            }, 0);
          }
        },
      });

      log("native:" + sym, "HOOK INSTALLED (library-load watcher)");
    });
  } catch (e) {
    log("native-lib", "hookLibraryLoad failed: " + e);
  }
}

function hookSuspiciousExports(m) {
  var pattern = /(emulator|detect|check|isEmu|Java_)/i;

  m.enumerateExports().forEach(function (e) {
    if (e.type !== "function" || !pattern.test(e.name)) return;

    try {
      Interceptor.attach(e.address, {
        onEnter: function () {
          log("detector-export", e.name + "() called");
        },
        onLeave: function (retval) {
          log("detector-export", e.name + "() -> " + retval);
        },
      });
    } catch (err) {
      log("detector-export", "could not hook " + e.name + ": " + err);
    }
  });
}

// --- Java-level self-termination blocking ---------------------------------
// This layer IS safe to swallow: these are Java methods that return normally,
// so if a detector tries to kill the app on detection we just... don't. No
// noreturn trap here because we never reach the native exit at all.
function hookProcessTermination() {
  try {
    var ProcessCls = Java.use("android.os.Process");
    safeOverload(ProcessCls, "killProcess", ["int"], function (pid) {
      log(
        "kill-block",
        "android.os.Process.killProcess(" +
          pid +
          ") blocked\n" +
          captureJavaStack(),
      );
      // intentionally not calling through -> swallows the kill
    });
  } catch (e) {
    log("kill-block", "Process.killProcess hook failed: " + e);
  }

  try {
    var SystemCls = Java.use("java.lang.System");
    safeOverload(SystemCls, "exit", ["int"], function (code) {
      log(
        "kill-block",
        "System.exit(" + code + ") blocked\n" + captureJavaStack(),
      );
    });
  } catch (e) {
    log("kill-block", "System.exit hook failed: " + e);
  }

  try {
    var RuntimeCls = Java.use("java.lang.Runtime");
    safeOverload(RuntimeCls, "exit", ["int"], function (code) {
      log(
        "kill-block",
        "Runtime.exit(" + code + ") blocked\n" + captureJavaStack(),
      );
    });
    safeOverload(RuntimeCls, "halt", ["int"], function (code) {
      log(
        "kill-block",
        "Runtime.halt(" + code + ") blocked\n" + captureJavaStack(),
      );
    });
  } catch (e) {
    log("kill-block", "Runtime.exit/halt hook failed: " + e);
  }
}

function captureJavaStack() {
  try {
    var ExceptionCls = Java.use("java.lang.Exception");
    var LogCls = Java.use("android.util.Log");
    return LogCls.getStackTraceString(ExceptionCls.$new());
  } catch (e) {
    return "<no Java stack available: " + e + ">";
  }
}

// --- native termination: OBSERVE, don't block -----------------------------
// You genuinely cannot make a noreturn function (abort/exit/_exit) return: the
// compiler drops a trap right after the call site, so "returning" lands on that
// trap -> SIGTRAP. So we only LOG native exits here as evidence ("detector tried
// to abort, here's the caller"). The real mitigation for self-kill is the
// spoofing above + the Java-level blocking -- stop the app deciding to die in
// the first place, don't try to catch it at the very last instruction.
//
// IMPORTANT: seeing "native abort() from liblog.so" in the log does NOT mean we
// caused a crash. liblog.so is how Android logs a fatal condition and then
// aborts; if you see it, look at the "abort-msg" line just above it for the
// real reason (e.g. an EGL failure) -- that is the thing to fix, not the abort.
function hookNativeTermination() {
  try {
    var libc = Process.getModuleByName("libc.so");

    // grab the abort message the framework/detector set, so a real crash is
    // readable instead of a bare SIGTRAP
    var setMsg = libc.findExportByName("android_set_abort_message");
    if (setMsg) {
      Interceptor.attach(setMsg, {
        onEnter: function (args) {
          var msg = "<none>";
          try {
            msg = args[0].readUtf8String();
          } catch (e) {}
          log(
            "abort-msg",
            msg + "  <- " + (callerModuleName(this.returnAddress) || "?"),
          );
        },
      });
      log("native:android_set_abort_message", "HOOK INSTALLED (observe)");
    }

    ["abort", "exit", "_exit"].forEach(function (sym) {
      var addr = libc.findExportByName(sym);
      if (!addr) return;

      Interceptor.attach(addr, {
        onEnter: function () {
          var caller = callerModuleName(this.returnAddress) || "<unknown>";
          var fromDetector = isTargetCaller(this.returnAddress);
          log(
            "term-observe",
            "native " +
              sym +
              "() from " +
              caller +
              (fromDetector ? "  [DETECTOR]" : "") +
              " -- letting it proceed (noreturn, cannot block safely)",
          );
        },
      });
      log("native:" + sym, "HOOK INSTALLED (observe only)");
    });

    // kill(pid, sig): if the detector tries to SIGKILL ourselves, neutralise it
    // by turning the signal into 0 (sig 0 is just an existence check, does
    // nothing). NOTE: do NOT set pid to -1 -- kill(-1, sig) blasts the whole
    // process group, which is way worse than the thing we're trying to stop.
    var killAddr = libc.findExportByName("kill");
    if (killAddr) {
      Interceptor.attach(killAddr, {
        onEnter: function (args) {
          var pid = args[0].toInt32();
          var sig = args[1].toInt32();

          if (pid === Process.id && isTargetCaller(this.returnAddress)) {
            log(
              "kill-block",
              "kill(self=" +
                pid +
                ", sig=" +
                sig +
                ") from " +
                callerModuleName(this.returnAddress) +
                " neutralised (sig->0)",
            );
            args[1] = ptr(0);
          }
        },
      });
      log("native:kill", "HOOK INSTALLED (scoped self-kill neutraliser)");
    }
  } catch (e) {
    log("kill-block", "hookNativeTermination failed: " + e);
  }
}

// --- Category 4: telephony / device information ---------------------------
function hookTelephony() {
  try {
    var TM = Java.use("android.telephony.TelephonyManager");
    var t = PROFILE.telephony;

    safeOverload(TM, "getDeviceId", [], function () {
      var v = t.deviceId || generateImei();
      log("Telephony", "getDeviceId() -> " + v);
      return v;
    });
    safeOverload(TM, "getImei", [], function () {
      var v = t.imei || generateImei();
      log("Telephony", "getImei() -> " + v);
      return v;
    });
    safeOverload(TM, "getLine1Number", [], function () {
      var v = t.line1Number || randomMsisdn();
      log("Telephony", "getLine1Number() -> " + v);
      return v;
    });
    safeOverload(TM, "getSubscriberId", [], function () {
      var v = t.subscriberId || "405854" + randomDigits(9); // plausible non-AVD IMSI
      log("Telephony", "getSubscriberId() -> " + v);
      return v;
    });
    safeOverload(TM, "getNetworkOperatorName", [], function () {
      var v = t.networkOperatorName;
      log("Telephony", "getNetworkOperatorName() -> " + v);
      return v;
    });
  } catch (e) {
    log("Telephony", "hookTelephony failed: " + e);
  }
}

// syscall(nr, ...): OBSERVE the exit-family syscalls from the detector. Same
// noreturn story as above -- forcing exit_group to "fail" and return would drop
// us back into a noreturn call site, so we only log. The number table is
// derived from the actual arch at runtime; the old hardcoded [93,94,131] were
// arm64 numbers and on this x86_64 image those are fchown/lchown/sigaltstack --
// so it was quietly poking sigaltstack (signal setup!) instead of exit.
function hookSyscallTermination() {
  try {
    var libc = Process.getModuleByName("libc.so");
    var syscallAddr = libc.findExportByName("syscall");
    if (!syscallAddr) return;

    var SYS =
      Process.arch === "x64"
        ? { exit: 60, exit_group: 231, tgkill: 234 }
        : Process.arch === "arm64"
          ? { exit: 93, exit_group: 94, tgkill: 131 }
          : Process.arch === "ia32"
            ? { exit: 1, exit_group: 252, tgkill: 270 }
            : { exit: 1, exit_group: 248, tgkill: 268 }; // arm

    var exitNumbers = [SYS.exit, SYS.exit_group, SYS.tgkill];

    Interceptor.attach(syscallAddr, {
      onEnter: function (args) {
        var nr = args[0].toInt32();
        if (
          exitNumbers.indexOf(nr) !== -1 &&
          isTargetCaller(this.returnAddress)
        ) {
          log(
            "syscall-observe",
            "syscall(" +
              nr +
              ") from " +
              callerModuleName(this.returnAddress) +
              " seen (observe only)",
          );
        }
      },
    });

    log("native:syscall", "HOOK INSTALLED (scoped syscall-exit observer)");
  } catch (e) {
    log("syscall-observe", "hookSyscallTermination failed: " + e);
  }
}

// --- lazy native layer installer ------------------------------------------
// The hot libc hooks and the syscall observer are only installed AFTER the app
// has drawn its first frame (first Activity.onResume + a short delay). By then
// eglInitialize() on the RenderThread has already succeeded, so wrapping libc
// can no longer break graphics bring-up. A timer fallback covers apps that
// somehow never resume an Activity.
var nativeLayerInstalled = false;

function installNativeLayerOnce(reason) {
  if (nativeLayerInstalled) return;
  if (!ANY_NATIVE) return;
  nativeLayerInstalled = true;
  log("native", "installing native layer now (" + reason + ")");
  Java.perform(function () {
    if (NATIVE_OBSERVERS) {
      hookLibraryLoad(); //     native dlopen watcher (detector-lib inspection)
      hookNativeTermination(); // native abort/exit/kill loggers (evidence)
    }
    if (NATIVE_FILE_HOOKS) installNativeFileHooks();
    if (NATIVE_SYSCALL_OBSERVER) hookSyscallTermination();
    log("native", "native layer installed.");
  });
}

function scheduleNativeAfterUI() {
  if (!ANY_NATIVE) {
    log("native", "native layer disabled -- Java-only mitigation (EGL-safe).");
    return;
  }
  try {
    var Activity = Java.use("android.app.Activity");
    Activity.onResume.implementation = function () {
      this.onResume(); // let the real resume run first
      // small delay so the first frame + EGL context are definitely up
      setTimeout(function () {
        installNativeLayerOnce("post-onResume");
      }, 500);
    };
    log("native", "native layer deferred until first Activity.onResume");
  } catch (e) {
    log("native", "could not defer via Activity.onResume: " + e);
  }
  // safety net in case no Activity ever resumes
  setTimeout(function () {
    installNativeLayerOnce("timer-fallback");
  }, 6000);
}

Java.perform(function () {
  log("init", "installing emulator-detection mitigations...");
  log("init", "arch=" + Process.arch + " pid=" + Process.id);

  Process.enumerateModules().forEach(function (m) {
    vlog("modules", m.name + " @ " + m.base);
  });

  // --- Java-level mitigations: safe, installed immediately ------------------
  // These use ART method instrumentation, not native libc interception, so
  // they do not touch the RenderThread's EGL init and are safe at startup.
  hookBuildInfo(); //       Category 1: Build information
  hookSystemProperties(); // Category 2: system properties
  hookFileExistsJava(); //  Category 3: emulator files/paths (Java probe)
  hookTelephony(); //       Category 4: telephony/device info
  hookProcessTermination(); // Java-level exit/kill blocking (returns normally)

  // --- ALL native interception is deferred until EGL is up (opt-in) ---------
  // Any Interceptor.attach installed before eglInitialize() (dlopen, abort,
  // libc file ops, syscall) can break the emulator's EGL driver load and crash
  // the RenderThread. So nothing native goes in until after the first frame.
  scheduleNativeAfterUI();

  log("init", "Java-layer hooks installed.");
});
