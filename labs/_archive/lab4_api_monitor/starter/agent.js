// Lab 3 starter: generic, config-driven Java API monitor (Frida 17+).
import Java from "frida-java-bridge";

var OPTIONS = { maxArgLen: 256, stackTrace: false };

// Turns any Java/JS value into a printable string without ever throwing.
function describe(v) {
  try {
    if (v === null || v === undefined) return "null";
    var s = typeof v === "string" ? JSON.stringify(v) : "" + v;
    return s.length > OPTIONS.maxArgLen ? s.substring(0, OPTIONS.maxArgLen) + "..." : s;
  } catch (e) {
    return "<unprintable>";
  }
}

// TODO 3 (do after the basics work): re-entrancy guard.
// describe() calls toString(), which may call a method we monitor. Keep a
// per-thread "busy" flag (Process.getCurrentThreadId()) and, while set, call
// the original method without logging.

function hookMethod(klass, spec, methodName) {
  var group = klass[methodName];
  if (!group || !group.overloads) {
    send({ event: "warn", message: "no such method: " + spec.class + "." + methodName });
    return 0;
  }
  var installed = 0;
  group.overloads.forEach(function (overload) {
    // TODO 2: replace overload.implementation. Inside it:
    //   - build a record {timestamp: Date.now(), category, class, method,
    //     signature, args, returnValue: null, exception: null}
    //     (signature: overload.argumentTypes.map(t => t.className).join(", "))
    //   - call the original with overload.apply(this, arguments)
    //   - on success fill record.returnValue = describe(retval)
    //   - on exception fill record.exception = describe(e), send the record,
    //     then RE-THROW e (do not swallow it!)
    //   - send(record) and return retval
    //   Hint: void methods have overload.returnType.className === "void".
    installed++;
  });
  return installed;
}

function installHooks(config) {
  if (config.options) Object.assign(OPTIONS, config.options);
  var hooks = 0, classes = 0, skipped = [];

  config.hooks.forEach(function (spec) {
    var klass;
    try {
      klass = Java.use(spec.class);
    } catch (e) {
      skipped.push(spec.class); // class not found / not visible yet
      return;
    }
    // TODO 1: "method" may be a string or a list of strings. Hook each name
    // with hookMethod(); count installed hooks and classes.
  });

  send({ event: "ready", hooks: hooks, classes: classes, skipped: skipped });
}

// With a spawned app the VM may not exist yet; retry until Java.perform works.
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
