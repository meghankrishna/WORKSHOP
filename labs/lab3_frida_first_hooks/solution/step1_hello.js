// Step 1 solution: your first hook.
import Java from "frida-java-bridge";

Java.perform(function () {
  var File = Java.use("java.io.File");

  File.exists.implementation = function () {
    var answer = this.exists();        // run the real method
    console.log("File.exists() was called");
    return answer;                     // the app gets its normal answer
  };

  console.log("hook installed on File.exists");
});
