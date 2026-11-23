# frida based script to hook android api calls and log them works with frida 17+ (they removed the java bridge from the runtime so we have to bundle it ourselves now, took me a while to figure this out)

# usage:
#   python3 api_monitor.py <package_name>
#   python3 api_monitor.py <package_name> --attach
#   python3 api_monitor.py <package_name> --device emulator-5554 --stack

import argparse
import datetime
import json
import os
import re
import sys
import threading

import frida

HERE = os.path.dirname(os.path.abspath(__file__))


def _project_dir():
    # works for both layouts: Config/ next to this script (flat), or
    # Source/ + Config/ side by side (script lives in Source/)
    if os.path.isdir(os.path.join(HERE, "Config")):
        return HERE
    return os.path.dirname(HERE)


PROJECT_DIR = _project_dir()

CONFIG_FILE = os.path.join(PROJECT_DIR, "Config", "api_config.json")
JS_FILE = os.path.join(HERE, "frida_hook_generator.js")
# JSON Lines: one JSON object per line, not a single JSON document
LOG_FILE = os.path.join(PROJECT_DIR, "Output", "api_monitor_logs.jsonl")

# same variable/default task1.sh uses when it starts frida-server
FRIDA_PORT = int(os.environ.get("FRIDA_PORT", "27042"))

BRIDGE_PKG = "frida-java-bridge"
OLD_PLACEHOLDER = "%CONFIG_PLACEHOLDER%"
SEP = "-" * 60

# used to tell the main loop to stop when the app dies / script unloads
stop_flag = threading.Event()


def resolve(path):
    # if the file isn't in cwd, check next to the script instead
    if os.path.isabs(path) or os.path.exists(path):
        return path
    alt = os.path.join(HERE, path)
    if os.path.exists(alt):
        return alt
    return path


def ensure_bridge(project_root, quiet=False):
    # need frida-java-bridge for Java.perform() to work at all on frida 17+ frida.PackageManager can fetch it without needing node/npm installed
    if os.path.isdir(os.path.join(project_root, "node_modules", BRIDGE_PKG)):
        return

    print("[*] %s not found, downloading it (needs internet)..." % BRIDGE_PKG)

    if not hasattr(frida, "PackageManager"):
        print("[!] this frida version doesn't have PackageManager (need >= 17.2)")
        print("    install it yourself with: npm install %s" % BRIDGE_PKG)
        sys.exit(1)

    pm = frida.PackageManager()

    if not quiet:

        def on_progress(phase, fraction, details):
            if phase in ("resolving-package", "downloading-package"):
                print("    " + phase, details or "")

        pm.on("install-progress", on_progress)

    try:
        result = pm.install(specs=[BRIDGE_PKG], project_root=project_root)
    except Exception as e:
        print("[!] couldn't install %s: %s" % (BRIDGE_PKG, e))
        print("    try manually: npm install %s (in %s)" % (BRIDGE_PKG, project_root))
        sys.exit(1)

    for pkg in result.packages:
        print("[+] installed %s@%s" % (pkg.name, pkg.version))


def build_agent(js_path, project_root):
    # compiles the agent (our js + the bridge) into one file frida can inject this is basically frida-compile but built into the python binding
    compiler = frida.Compiler()

    diagnostics = []
    compiler.on("diagnostics", lambda diags: diagnostics.extend(diags))

    # entrypoint has to be an absolute path or it breaks (spent an hour on this)
    try:
        return compiler.build(
            os.path.abspath(js_path),
            project_root=os.path.abspath(project_root),
            bundle_format="iife",
        )
    except TypeError:
        # older frida doesn't have bundle_format param
        return compiler.build(
            os.path.abspath(js_path), project_root=os.path.abspath(project_root)
        )
    except Exception as e:
        print("[!] failed to compile %s: %s" % (js_path, e))
        for d in diagnostics:
            print("    ", d)
        sys.exit(1)


def get_device(device_id=None, timeout=10):
    manager = frida.get_device_manager()

    if device_id:
        return manager.get_device(device_id, timeout=timeout)

    # try to find a usb/emulator device first
    for d in manager.enumerate_devices():
        if d.type in ("usb", "emulator") or "555" in d.id or "emulator" in d.id:
            return d

    # frida.get_device() with no args doesn't actually work (TypeError), so fall back to these instead
    try:
        return frida.get_usb_device(timeout=timeout)
    except Exception:
        pass

    try:
        # frida-server port forwarded by task1.sh (5555 is adb's port, not frida's)
        return manager.add_remote_device("127.0.0.1:%d" % FRIDA_PORT)
    except Exception as e:
        raise RuntimeError("couldn't find a frida device: %s" % e)


class CallLogger:
    # writes every hook hit to a jsonl file (one json object per line) opens the file right away so we always get an output file even if nothing ends up getting hooked
    def __init__(self, path):
        self.path = path
        self.count = 0
        self.lock = threading.Lock()
        self.fh = open(path, "w", encoding="utf-8")
        self.fh.flush()

    def write(self, record):
        with self.lock:
            json.dump(
                record, self.fh, default=str
            )  # default=str so weird values dont crash it
            self.fh.write("\n")
            self.fh.flush()
            self.count += 1

    def close(self):
        with self.lock:
            try:
                self.fh.flush()
                self.fh.close()
            except Exception:
                pass


def fmt_time(ms):
    try:
        dt = datetime.datetime.fromtimestamp(float(ms) / 1000.0)
    except (TypeError, ValueError):
        dt = datetime.datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def make_on_message(logger):
    # handles messages coming back from the js side wrapped everything in .get() calls so a weird payload doesn't just kill the callback thread silently
    def on_message(message, data):
        mtype = message.get("type")

        if mtype == "send":
            payload = message.get("payload")

            if not isinstance(payload, dict):
                print("[js]", payload)
                return

            event = payload.get("event")

            if event == "ready":
                android_ver = payload.get("androidVersion")
                extra = " | android %s" % android_ver if android_ver else ""
                print(
                    "[+] hooks installed: %d methods across %d classes%s"
                    % (payload.get("hooks", 0), payload.get("classes", 0), extra)
                )
                for name in payload.get("skipped", []):
                    print("    [-] skipped (class not found): %s" % name)
                print(SEP)
                return

            if event in ("info", "warn"):
                print("[js]", payload.get("message", ""))
                return

            if event == "fatal":
                print("[!] agent error:", payload.get("message", ""))
                stop_flag.set()
                return

            # no "event" key means its an actual hook/call record
            args = payload.get("args") or []
            args_str = ", ".join(str(a) for a in args) if args else "None"

            if payload.get("exception"):
                ret_val = "EXCEPTION: %s" % payload["exception"]
            else:
                ret_val = str(payload.get("returnValue"))

            print(
                "[%s] [%s] %s.%s"
                % (
                    fmt_time(payload.get("timestamp")),
                    str(payload.get("category", "general")).upper(),
                    payload.get("class", "?"),
                    payload.get("method", "?"),
                )
            )
            if payload.get("signature") is not None:
                print("    sig:", payload["signature"])
            print("    args:", args_str)
            print("    ret: ", ret_val)
            if payload.get("stack"):
                print("    stack:\n" + payload["stack"])
            print(SEP)

            logger.write(payload)

        elif mtype == "log":
            # console.log in the agent shows up as type "log" not "send" (took forever to realize this, my print statements were just vanishing)
            print(
                "[js:%s] %s"
                % (message.get("level", "info"), message.get("payload", ""))
            )

        elif mtype == "error":
            desc = message.get("description", "")
            print("[!] frida error:", desc)
            if message.get("stack"):
                print(message["stack"])
            if "'Java' is not defined" in desc:
                print("[!] ^ this means the agent got injected without the java bridge")
                print("      this script should build that in automatically, so if you")
                print(
                    "      swapped the js file check it has: import Java from 'frida-java-bridge'"
                )
                stop_flag.set()

    return on_message


def parse_args(argv):
    p = argparse.ArgumentParser(description="frida android api monitor")
    p.add_argument("package", help="target package, e.g. jakhar.aseem.diva")
    p.add_argument("--attach", action="store_true", help="attach instead of spawning")
    p.add_argument("--device", default=None, help="frida device id")
    p.add_argument("--config", default=CONFIG_FILE)
    p.add_argument("--script", default=JS_FILE)
    p.add_argument("--log", default=LOG_FILE)
    p.add_argument(
        "--stack", action="store_true", help="grab a java stack trace per call"
    )
    p.add_argument(
        "--kill", action="store_true", help="kill app on exit (only if we spawned it)"
    )
    p.add_argument(
        "--dump-agent",
        metavar="PATH",
        default=None,
        help="just write the compiled agent here and quit, for debugging",
    )
    return p.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])

    config_path = resolve(args.config)
    js_path = resolve(args.script)
    project_root = os.path.dirname(os.path.abspath(js_path)) or HERE

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = f.read()
        with open(js_path, "r", encoding="utf-8") as f:
            js_source = f.read()
    except FileNotFoundError as e:
        print("[!] missing file:", e.filename)
        sys.exit(1)

    # parse config here so a json typo shows up as a clear python error instead of failing weirdly inside the injected script
    try:
        config_obj = json.loads(raw_config)
    except ValueError as e:
        print("[!] %s is not valid json: %s" % (config_path, e))
        sys.exit(1)

    if args.stack:
        config_obj.setdefault("options", {})["stackTrace"] = True

    # check if this is an old style agent (uses the placeholder string) or an esm one with real imports
    is_esm = (
        re.search(r"^\s*import\s+.+\s+from\s+['\"]", js_source, re.MULTILINE)
        is not None
    )
    legacy_mode = (not is_esm) and OLD_PLACEHOLDER in js_source

    if legacy_mode:
        print("[*] legacy agent detected, injecting without building anything")
        if int(str(frida.__version__).split(".")[0]) >= 17:
            print(
                "[!] warning: frida %s doesn't bundle the java bridge anymore"
                % frida.__version__
            )
            print("    this will probably fail with \"'Java' is not defined\"")
            print(
                "    switch to the esm agent instead (import Java from 'frida-java-bridge')"
            )
        agent_source = js_source.replace(
            OLD_PLACEHOLDER, json.dumps(config_obj, separators=(",", ":"))
        )
    else:
        ensure_bridge(project_root)
        agent_source = build_agent(js_path, project_root)
        print(
            "[+] agent built: %.1f KB (frida %s)"
            % (len(agent_source) / 1024.0, frida.__version__)
        )

    if args.dump_agent:
        with open(args.dump_agent, "w", encoding="utf-8") as f:
            f.write(agent_source)
        print("[+] wrote compiled agent to", os.path.abspath(args.dump_agent))
        return

    log_dir = os.path.dirname(os.path.abspath(args.log))
    os.makedirs(log_dir, exist_ok=True)
    logger = CallLogger(args.log)
    print("[+] logging to", os.path.abspath(args.log))

    device = None
    session = None
    script = None
    pid = None
    spawned = False

    try:
        device = get_device(args.device)
        print("[+] using device: %s (%s)" % (device.name, device.id))

        if args.attach:
            session = device.attach(args.package)
            print("[+] attached to running process:", args.package)
        else:
            pid = device.spawn([args.package])
            spawned = True
            session = device.attach(pid)
            print("[+] spawned %s (pid %d)" % (args.package, pid))

        session.on("detached", lambda *a: stop_flag.set())

        script = session.create_script(agent_source)
        script.on("message", make_on_message(logger))
        script.on("destroyed", lambda *a: stop_flag.set())
        script.load()

        if not legacy_mode:
            # send the hook config over rpc before resuming so hooks are ready before any app code actually runs
            script.exports_sync.init(config_obj)

        if spawned:
            device.resume(pid)

        print("[+] monitoring, ctrl+c to stop\n")

        # used to just do sys.stdin.read() here but that returns immediately if stdin is piped/redirected, so the script would exit right after starting. this waits properly instead
        while not stop_flag.wait(0.5):
            pass

    except frida.NotSupportedError as e:
        print("[!] error:", e)
        if not args.attach:
            print("    is the app installed? is frida-server running?")
            print("    if it's already open, try --attach")
    except KeyboardInterrupt:
        print("\n[!] stopping...")
    except Exception as e:
        print("[!] error:", e)
    finally:
        try:
            if script is not None:
                script.unload()
        except Exception:
            pass
        try:
            if session is not None and not session.is_detached:
                session.detach()
        except Exception:
            pass
        if args.kill and spawned and pid is not None and device is not None:
            try:
                device.kill(pid)
            except Exception:
                pass

        logger.close()
        print("[+] recorded %d calls -> %s" % (logger.count, os.path.abspath(args.log)))


if __name__ == "__main__":
    main()
