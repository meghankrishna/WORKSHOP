// Step 4 solution: hooks come from a config file.
import Java from "frida-java-bridge";

function hookOne(className, methodName) {
  var klass = Java.use(className);
  var group = klass[methodName];
  if (!group) {
    console.log("no such method: " + className + "." + methodName);
    return;
  }

  group.overloads.forEach(function (overload) {
    var signature = overload.argumentTypes
      .map(function (t) { return t.className; })
      .join(", ");

    overload.implementation = function () {
      var result = overload.apply(this, arguments);
      console.log(className + "." + methodName + "(" + signature + ") -> " + result);
      return result;
    };
  });
  console.log("hooked " + className + "." + methodName);
}

rpc.exports = {
  init: function (config) {
    Java.perform(function () {
      config.hooks.forEach(function (entry) {
        try {
          hookOne(entry["class"], entry.method);
        } catch (e) {
          console.log("could not hook " + entry["class"] + ": " + e);
        }
      });
    });
    return true;
  },
};
