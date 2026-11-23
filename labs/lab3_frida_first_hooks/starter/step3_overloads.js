// Step 3: overloads: one method name, several versions.
// android.util.Log.d has (tag, message) and (tag, message, error).
// If you hook "Log.d" the lazy way, Frida complains it is ambiguous.
// Goal: hook EVERY version with a loop.
import Java from "frida-java-bridge";

Java.perform(function () {
  var Log = Java.use("android.util.Log");

  // Log.d.overloads is a list with one entry per version.
  Log.d.overloads.forEach(function (overload) {
    // A readable name for this version, e.g. "java.lang.String, java.lang.String"
    var signature = overload.argumentTypes
      .map(function (t) { return t.className; })
      .join(", ");
    console.log("hooking Log.d(" + signature + ")");

    // TODO: set overload.implementation = function () { ... }
    // Inside:
    //   - print the arguments. `arguments` is the list of everything passed in:
    //       console.log("Log.d(" + signature + ") args: " +
    //                   Array.prototype.slice.call(arguments).join(" | "));
    //   - call the REAL version and return its result:
    //       return overload.apply(this, arguments);
  });
});
