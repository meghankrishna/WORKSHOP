// Step 2: log WHAT was asked and WHAT the answer was.
// Goal: print lines like   File.exists("/data/user/0/...") -> true
import Java from "frida-java-bridge";

Java.perform(function () {
  var File = Java.use("java.io.File");

  File.exists.implementation = function () {
    var answer = this.exists();

    // TODO: `this` is the File object being asked. Its path is this.getPath().
    // Print:  File.exists("<path>") -> <answer>
    // Hint:   console.log('File.exists("' + this.getPath() + '") -> ' + answer);

    return answer;
  };

  console.log("hook installed on File.exists (with details)");
});
