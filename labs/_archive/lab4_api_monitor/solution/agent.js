// Lab 3 solution: generic, config-driven Java API monitor (Frida 17+).
import Java from "frida-java-bridge";

var OPTIONS = { maxArgLen: 256, stackTrace: false };

function describe(v) {
  try {
    if (v === null || v === undefined) return "null";
    var s = typeof v === "string" ? JSON.stringify(v) : "" + v;
    return s.length > OPTIONS.maxArgLen
      ? s.substring(0, OPTIONS.maxArgLen) + "...<+" + (s.length - OPTIONS.maxArgLen) + " chars>"
      : s;
  } catch (e) {
    return "<unprintable>";
  }
}

function describeError(e) {
  try {
    if (e && e.$className !== undefined) return e.$className + ": " + e;
    return (e && e.message) || String(e);
  } catch (x) {
    return "<unprintable exception>";
  }
}

// Re-entrancy guard (per thread). describe() calls toString(), which may call
// a monitored method; while a thread is inside our logging code, monitored
// calls pass straight through to the original. Calls the app makes from
// inside the real method are still recorded.
var busy = {};
function inMonitor() { return busy[Process.getCurrentThreadId()] === true; }
function guarded(fn) {
  var tid = Process.getCurrentThreadId();
  busy[tid] = true;
  try { return fn(); } finally { delete busy[tid]; }
}

var Throwable = null, Log = null;
function stackTrace() {
  try { return Log.getStackTraceString(Throwable.$new()); } catch (e) { return null; }
}

function methodNames(spec) {
  var m = spec.method !== undefined ? spec.method : spec.methods;
  if (typeof m === "string") return [m];
  if (Array.isArray(m)) return m;
  return [];
}

function hookMethod(klass, spec, methodName) {
  var group = klass[methodName];
  if (!group || !group.overloads) {
    send({ event: "warn", message: "no such method: " + spec.class + "." + methodName });
    return 0;
  }
  var installed = 0;
  group.overloads.forEach(function (overload) {
    var signature = null, isVoid = false;
    try {
      signature = overload.argumentTypes.map(function (t) { return t.className; }).join(", ");
      isVoid = overload.returnType.className === "void";
    } catch (e) {}

    // optional: only hook the overload named in the config
    if (Array.isArray(spec.overload) && signature !== spec.overload.join(", ")) return;

    overload.implementation = function () {
      if (inMonitor()) return overload.apply(this, arguments);

      var callArgs = arguments;
      var rec = guarded(function () {
        var r = {
          timestamp: Date.now(),
          category: spec.category || "general",
          class: spec.class,
          method: methodName,
          signature: signature,
          args: Array.prototype.map.call(callArgs, describe),
          returnValue: null,
          exception: null,
        };
        if (OPTIONS.stackTrace) r.stack = stackTrace();
        return r;
      });

      var retval;
      try {
        retval = overload.apply(this, arguments);
      } catch (e) {
        guarded(function () { rec.exception = describeError(e); send(rec); });
        throw e; // re-throw the REAL exception: app behaviour must not change
      }
      guarded(function () { rec.returnValue = isVoid ? "void" : describe(retval); send(rec); });
      return retval;
    };
    installed++;
  });
  return installed;
}

function installHooks(config) {
  if (config.options) Object.assign(OPTIONS, config.options);
  if (OPTIONS.stackTrace) {
    try { Throwable = Java.use("java.lang.Throwable"); Log = Java.use("android.util.Log"); }
    catch (e) { OPTIONS.stackTrace = false; }
  }
  var hooks = 0, classes = 0, skipped = [];

  config.hooks.forEach(function (spec) {
    var klass;
    try { klass = Java.use(spec["class"]); }
    catch (e) { skipped.push(spec["class"]); return; }
    spec.class = spec["class"];

    var before = hooks;
    methodNames(spec).forEach(function (name) { hooks += hookMethod(klass, spec, name); });
    if (hooks > before) classes++;
  });

  send({ event: "ready", hooks: hooks, classes: classes, skipped: skipped });
}

function whenJavaReady(cb, attempt) {
  attempt = attempt || 0;
  try {
    Java.perform(cb);
  } catch (e) {
    if (attempt > 800) return send({ event: "fatal", message: "Java VM never came up" });
    setTimeout(function () { whenJavaReady(cb, attempt + 1); }, 25);
  }
}

rpc.exports = {
  init: function (config) {
    whenJavaReady(function () { installHooks(config); });
    return true;
  },
};
