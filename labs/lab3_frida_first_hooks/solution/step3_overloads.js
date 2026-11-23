// Step 3 solution: hook every overload of android.util.Log.d
import Java from "frida-java-bridge";

Java.perform(function () {
  var Log = Java.use("android.util.Log");

  Log.d.overloads.forEach(function (overload) {
    var signature = overload.argumentTypes
      .map(function (t) { return t.className; })
      .join(", ");
    console.log("hooking Log.d(" + signature + ")");

    overload.implementation = function () {
      console.log("Log.d(" + signature + ") args: " +
                  Array.prototype.slice.call(arguments).join(" | "));
      return overload.apply(this, arguments);
    };
  });
});
