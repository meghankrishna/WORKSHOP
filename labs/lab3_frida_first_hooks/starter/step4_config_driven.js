// Step 4: read the list of things to watch from a CONFIG FILE.
// Run with:  python3 run_frida.py <package> starter/step4_config_driven.js --config apis_demo.json
//
// run_frida.py reads apis_demo.json and hands it to the init() function below:
//   { "hooks": [ {"class": "java.io.File", "method": "exists"}, ... ] }
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
      // TODO: print one line:  ClassName.method(signature) -> result
      return result;
    };
  });
  console.log("hooked " + className + "." + methodName);
}

rpc.exports = {
  init: function (config) {
    Java.perform(function () {
      // TODO: loop over config.hooks (it is a list). For every entry call
      //       hookOne(entry["class"], entry.method);
      // Hint: config.hooks.forEach(function (entry) { ... });
    });
    return true;
  },
};
