// Step 1: your first hook.
// Goal: every time the app calls File.exists(), print a line, and let the app
// get its normal answer.
import Java from "frida-java-bridge";

Java.perform(function () {
  // Get a handle on the Java class we want to watch.
  var File = Java.use("java.io.File");

  // TODO: replace File.exists with your own function.
  // Inside it you must:
  //   1. call the REAL method:        var answer = this.exists();
  //   2. print a message:             console.log("File.exists() was called");
  //   3. give the app its answer:     return answer;
  //
  // Shape of the code:
  //   File.exists.implementation = function () {
  //     ...
  //   };

  console.log("hook installed on File.exists");
});
