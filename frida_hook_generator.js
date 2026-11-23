import Java from "frida-java-bridge";

var OPTIONS = {
  stackTrace: false, // grab a java stack trace per call, off by default cause its noisy
  maxArgLen: 256, // cut off long args/returns after this many chars
  maxBytes: 64, // how many bytes of a byte[] to hex dump
};

var RESERVED_KEYS = ["options", "settings"];

function emit(record) {
  try {
    send(record);
  } catch (e) {
    /* nothing to do if the channel is gone */
  }
}

function notify(event, message, extra) {
  var payload = { event: event, message: message };
  if (extra) {
    for (var k in extra) {
      payload[k] = extra[k];
    }
  }
  emit(payload);
}

function truncate(s) {
  s = String(s);
  if (s.length <= OPTIONS.maxArgLen) {
    return s;
  }
  return (
    s.substring(0, OPTIONS.maxArgLen) +
    "...<+" +
    (s.length - OPTIONS.maxArgLen) +
    " chars>"
  );
}

// turns any arg/return value into a printable string without ever throwing (calling toString() on some half init'd object could crash the app)
function describe(v) {
  try {
    if (v === null || v === undefined) {
      return "null";
    }

    var t = typeof v;
    if (t === "number" || t === "boolean") {
      return String(v);
    }
    if (t === "string") {
      return truncate(JSON.stringify(v));
    }

    if (Array.isArray(v)) {
      return describeArray(v);
    }

    if (v.$className !== undefined) {
      // java object wrapper
      try {
        return truncate("" + v);
      } catch (e) {
        return "<" + v.$className + ">";
      }
    }
    return truncate(String(v));
  } catch (e) {
    return "<unprintable>";
  }
}

// byte[] / int[] / Object[] all show up as plain js arrays
function describeArray(arr) {
  if (arr.length === 0) {
    return "[]";
  }

  var numeric = true;
  for (var i = 0; i < arr.length && i < 8; i++) {
    if (typeof arr[i] !== "number") {
      numeric = false;
      break;
    }
  }

  if (!numeric) {
    var parts = [];
    for (var j = 0; j < arr.length && j < 8; j++) {
      parts.push(describe(arr[j]));
    }
    if (arr.length > 8) {
      parts.push("...(" + arr.length + " total)");
    }
    return "[" + parts.join(", ") + "]";
  }

  // looks numeric, treat it like a byte array and hex dump it
  var n = Math.min(arr.length, OPTIONS.maxBytes);
  var hex = [],
    ascii = [];
  for (var k = 0; k < n; k++) {
    var b = arr[k] & 0xff;
    hex.push(("0" + b.toString(16)).slice(-2));
    ascii.push(b >= 0x20 && b < 0x7f ? String.fromCharCode(b) : ".");
  }
  var out =
    "byte[" + arr.length + "] " + hex.join(" ") + ' | "' + ascii.join("") + '"';
  if (arr.length > n) {
    out += " ...";
  }
  return out;
}

function describeError(e) {
  try {
    if (e === null || e === undefined) {
      return "unknown error";
    }
    if (e.$className !== undefined) {
      // java throwable wrapper
      try {
        return e.$className + ": " + e;
      } catch (x) {
        return e.$className;
      }
    }
    var name = e.name ? e.name + ": " : "";
    return truncate(name + (e.message !== undefined ? e.message : String(e)));
  } catch (x) {
    return "<unprintable exception>";
  }
}

function toMethods(m) {
  if (m === undefined || m === null) {
    return ["*"];
  }
  if (typeof m === "string") {
    return [m];
  }
  if (Array.isArray(m) && m.length > 0) {
    return m;
  }
  return ["*"];
}

// entries might say "method" (single) or "methods" (list), have to check both or it'll silently fall back to wildcard and hook way too much
function methodsOf(entry) {
  if (entry.methods !== undefined && entry.methods !== null) {
    return toMethods(entry.methods);
  }
  if (entry.method !== undefined && entry.method !== null) {
    return toMethods(entry.method);
  }
  return ["*"];
}

function normalizeConfig(raw) {
  var specs = [];
  if (!raw || typeof raw !== "object") {
    return specs;
  }

  var opts = raw.options || raw.settings;
  if (opts && typeof opts === "object") {
    for (var o in opts) {
      OPTIONS[o] = opts[o];
    }
  }

  if (Array.isArray(raw.hooks)) {
    raw.hooks.forEach(function (h) {
      specs.push({
        category: h.category || "general",
        className: h["class"] || h.className,
        methods: methodsOf(h),
      });
    });
    return specs;
  }

  var root =
    raw.categories && typeof raw.categories === "object" ? raw.categories : raw;

  Object.keys(root).forEach(function (category) {
    if (RESERVED_KEYS.indexOf(category) !== -1) {
      return;
    }
    var entry = root[category];

    if (Array.isArray(entry)) {
      entry.forEach(function (item) {
        if (typeof item === "string") {
          specs.push({ category: category, className: item, methods: ["*"] });
        } else if (item && typeof item === "object") {
          specs.push({
            category: category,
            className: item["class"] || item.className,
            methods: methodsOf(item),
          });
        }
      });
    } else if (entry && typeof entry === "object") {
      Object.keys(entry).forEach(function (cls) {
        specs.push({
          category: category,
          className: cls,
          methods: toMethods(entry[cls]),
        });
      });
    }
  });

  return specs;
}

//stack traces (only if OPTIONS.stackTrace is on)
var Throwable = null;
var Log = null;
var buildingTrace = false; // stop it from recursing if Log/Throwable end up hooked too

function stackTrace() {
  if (buildingTrace || Throwable === null || Log === null) {
    return null;
  }
  buildingTrace = true;
  try {
    return Log.getStackTraceString(Throwable.$new());
  } catch (e) {
    return null;
  } finally {
    buildingTrace = false;
  }
}

// re-entrancy guard (per thread)
// describe()/describeError()/stackTrace() call back into Java (toString(),
// Log.getStackTraceString, ...). if the config monitors a class those helpers
// use -- e.g. java.lang.StringBuilder -- the hook would trigger itself forever
// and crash the app. while a thread is inside our own logging code, any
// monitored call it makes is passed straight through to the original.
// only the logging code is guarded: monitored calls the app makes from inside
// the real method (overload.apply) are still recorded.
var busyThreads = {};

function inMonitor() {
  return busyThreads[Process.getCurrentThreadId()] === true;
}

function guarded(fn) {
  var tid = Process.getCurrentThreadId();
  busyThreads[tid] = true;
  try {
    return fn();
  } finally {
    delete busyThreads[tid];
  }
}

//actual hooking
function declaredMethodNames(klass) {
  var seen = {};
  try {
    var methods = klass.class.getDeclaredMethods();
    for (var i = 0; i < methods.length; i++) {
      seen[methods[i].getName()] = true;
    }
  } catch (e) {
    // obfuscated class or we cant see it
  }
  return Object.keys(seen);
}

function hookMethod(klass, spec, methodName) {
  var group = klass[methodName];
  if (group === undefined || group === null || group.overloads === undefined) {
    notify("warn", "no such method: " + spec.className + "." + methodName);
    return 0;
  }
  var installed = 0;
  group.overloads.forEach(function (overload) {
    // overload is captured per loop iteration so each replacement wraps exactly the overload it replaced, not some other one
    var signature,
      isVoid = false;
    try {
      signature = overload.argumentTypes
        .map(function (t) {
          return t.className;
        })
        .join(", ");
    } catch (e) {
      signature = null;
    }
    try {
      isVoid = overload.returnType && overload.returnType.className === "void";
    } catch (e) {
      // just leave isVoid false
    }

    try {
      overload.implementation = function () {
        // called from inside our own logging code -> don't log, just run it
        if (inMonitor()) {
          return overload.apply(this, arguments);
        }

        var callArgs = arguments;
        var record = guarded(function () {
          var args = [];
          for (var i = 0; i < callArgs.length; i++) {
            args.push(describe(callArgs[i]));
          }
          var r = {
            timestamp: Date.now(),
            category: spec.category,
            class: spec.className,
            method: methodName,
            signature: signature,
            args: args,
            returnValue: null,
            exception: null,
          };
          if (OPTIONS.stackTrace) {
            r.stack = stackTrace();
          }
          return r;
        });

        var retval;
        try {
          retval = overload.apply(this, arguments);
        } catch (e) {
          guarded(function () {
            record.exception = describeError(e);
            emit(record);
          });
          // rethrow the actual error object, not a string, otherwise the app's own catch (IOException e) stops matching and it changes app behaviour without us realizing
          throw e;
        }

        guarded(function () {
          record.returnValue = isVoid ? "void" : describe(retval);
          emit(record);
        });
        return retval;
      };
      installed++;
    } catch (e) {
      notify(
        "warn",
        "cannot hook " +
          spec.className +
          "." +
          methodName +
          "(" +
          signature +
          "): " +
          describeError(e),
      );
    }
  });

  return installed;
}

function safeAndroidVersion() {
  try {
    return Java.androidVersion;
  } catch (e) {
    return null;
  }
}

function installHooks(rawConfig) {
  var specs = normalizeConfig(rawConfig); // this also applies OPTIONS overrides

  if (OPTIONS.stackTrace) {
    try {
      Throwable = Java.use("java.lang.Throwable");
      Log = Java.use("android.util.Log");
    } catch (e) {
      notify("warn", "stack traces unavailable: " + describeError(e));
    }
  }

  var hookCount = 0;
  var classCount = 0;
  var skipped = [];

  specs.forEach(function (spec) {
    if (!spec.className) {
      return;
    }

    var klass;
    try {
      klass = Java.use(spec.className);
    } catch (e) {
      // class isn't loaded yet, or its in an app classloader we cant see
      skipped.push(spec.className);
      return;
    }

    var names = spec.methods;
    if (names.length === 1 && names[0] === "*") {
      names = declaredMethodNames(klass);
      names.push("$init");
    }

    var before = hookCount;
    names.forEach(function (name) {
      hookCount += hookMethod(klass, spec, name);
    });
    if (hookCount > before) {
      classCount++;
    }
  });

  emit({
    event: "ready",
    hooks: hookCount,
    classes: classCount,
    skipped: skipped,
    androidVersion: safeAndroidVersion(),
  });
}

// cant just call Java.perform() straight away.
// with device.spawn() the app is suspended right at its entry point, so when this script loads the ART VM might not even be mapped in yet, and
// Java.perform() throws "Java API not available" if you call it too early. the agent thread keeps running while the app is suspended though,
// so we just retry on a timer until it works (becomes available after device.resume())
// we try perform() first before polling, because if the VM exists but the app classloader isnt ready the bridge just queues the callback internally and
// fires it asap - which still catches calls made during Application.onCreate(). polling first would install the hooks later and miss that early stuff

var POLL_MS = 25;
var MAX_ATTEMPTS = 800; // ~20s total

function whenJavaReady(callback, attempt) {
  attempt = attempt || 0;

  if (typeof Java === "undefined" || Java === null) {
    notify(
      "fatal",
      "frida-java-bridge never loaded, was this agent actually built with frida.Compiler()?",
    );
    return;
  }

  try {
    Java.perform(callback);
    return;
  } catch (e) {
    // just retry below, no need to spam a message every single attempt
  }

  if (attempt >= MAX_ATTEMPTS) {
    notify(
      "fatal",
      "java vm never came up after " +
        (POLL_MS * MAX_ATTEMPTS) / 1000 +
        "s, is this even a java process?",
    );
    return;
  }

  setTimeout(function () {
    whenJavaReady(callback, attempt + 1);
  }, POLL_MS);
}

// rpc entry point
// api_monitor.py calls init(config) right after script.load(), before resuming
rpc.exports = {
  init: function (config) {
    whenJavaReady(function () {
      installHooks(config);
    });
    return true;
  },
};
