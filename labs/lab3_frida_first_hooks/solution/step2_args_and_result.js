// Step 2 solution: log what was asked and what the answer was.
import Java from "frida-java-bridge";

Java.perform(function () {
  var File = Java.use("java.io.File");

  File.exists.implementation = function () {
    var answer = this.exists();
    console.log('File.exists("' + this.getPath() + '") -> ' + answer);
    return answer;
  };

  console.log("hook installed on File.exists (with details)");
});
