"""UCI proxy that runs Stockfish on a remote server over SSH.

The chess GUI starts this script as a local UCI engine. The script runs
the system ssh client, which starts Stockfish on the server, and relays
the UCI lines between the GUI (stdin/stdout) and the engine (the ssh
pipes). Settings come from config.json, read from the directory of
sys.argv[0].
"""

import json
import logging
import os
import queue
import shutil
import subprocess  # nosec B404 # argv list only, no shell=True
import sys
import threading
import time


def setup_logging(config):
    """Log at DEBUG level to log_file if logging_enabled is true.

    Otherwise only CRITICAL messages are emitted, on stderr.
    """
    if config.get("logging_enabled", False):
        logging.basicConfig(
            filename=config.get("log_file", "debug.log"),
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        logging.info("Logging initialized.")
    else:
        logging.basicConfig(level=logging.CRITICAL)


def load_config():
    """Return the parsed config.json found in the directory of sys.argv[0].

    The current directory is used when sys.argv[0] has no directory part.
    Exit with status 1 if the file is missing or is not valid JSON.
    """
    config_path = os.path.join(os.path.dirname(sys.argv[0]) or ".", "config.json")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Configuration file '{config_path}' not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing configuration file: {e}", file=sys.stderr)
        sys.exit(1)


def handle_output(process, output_queue, terminate_event):
    """Forward each engine line to the GUI and copy it to output_queue.

    Run in a daemon thread until EOF on the ssh stdout, or until
    terminate_event is set (checked between two lines). The copy lets
    wait_for_marker look for uciok, readyok and bestmove.
    """
    try:
        while not terminate_event.is_set():
            line = process.stdout.readline()
            if line == "":
                # EOF reached
                break
            line = line.rstrip("\r\n")
            logging.debug("STDOUT: %s", line)
            output_queue.put(line)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
    except Exception:
        logging.exception("Error reading stdout")


def handle_stderr(process, terminate_event):
    """Log each line of the ssh stderr as a warning, never sent to the GUI.

    Run in a daemon thread until EOF or until terminate_event is set.
    """
    try:
        while not terminate_event.is_set():
            line = process.stderr.readline()
            if line == "":
                break
            line = line.rstrip("\r\n")
            logging.warning("STDERR: %s", line)
    except Exception:
        logging.exception("Error reading stderr")


def wait_for_marker(output_queue, marker, timeout=None):
    """Consume output_queue until a line contains marker.

    Return True when such a line is read. Return False on error, or at
    the first 0.5 s without output once timeout seconds have elapsed
    (timeout None waits forever). Lines read here are only removed from
    the queue: handle_output sends every line to the GUI on its own.
    """
    start = time.time()
    try:
        while True:
            try:
                output = output_queue.get(timeout=0.5)
            except queue.Empty:
                if timeout is not None and (time.time() - start) > timeout:
                    logging.error("Timeout waiting for marker '%s'", marker)
                    return False
                continue
            if marker in output:
                logging.debug("Marker '%s' found.", marker)
                return True
    except Exception:
        logging.exception("Error in wait_for_marker")
        return False


def configure_stockfish(process, config, output_queue):
    """Apply the engine options of config.json before the GUI takes over.

    Send uci and wait for uciok. Send a setoption for each of sf_threads,
    sf_hash, sf_multipv and sf_ponder found in the config, and for each
    entry of sf_options. Then send isready and wait for readyok. Errors
    are logged, never fatal.
    """
    logging.info("Initializing Stockfish with custom configuration...")

    # Send uci first
    try:
        process.stdin.write("uci\n")
        process.stdin.flush()
        wait_for_marker(output_queue, "uciok", timeout=5)
    except Exception:
        logging.exception("Failed to initialize UCI")
        return

    # Configure threads
    if "sf_threads" in config:
        threads = config["sf_threads"]
        try:
            process.stdin.write(f"setoption name Threads value {threads}\n")
            process.stdin.flush()
            logging.info("Setting Stockfish threads to %s", threads)
        except Exception:
            logging.exception("Failed to set threads")

    # Configure hash
    if "sf_hash" in config:
        hash_mb = config["sf_hash"]
        try:
            process.stdin.write(f"setoption name Hash value {hash_mb}\n")
            process.stdin.flush()
            logging.info("Setting Stockfish hash to %sMB", hash_mb)
        except Exception:
            logging.exception("Failed to set hash")

    # Configure MultiPV
    if "sf_multipv" in config:
        multipv = config["sf_multipv"]
        try:
            process.stdin.write(f"setoption name MultiPV value {multipv}\n")
            process.stdin.flush()
            logging.info("Setting Stockfish MultiPV to %s", multipv)
        except Exception:
            logging.exception("Failed to set MultiPV")

    # Configure Ponder
    if "sf_ponder" in config:
        ponder = "true" if config["sf_ponder"] else "false"
        try:
            process.stdin.write(f"setoption name Ponder value {ponder}\n")
            process.stdin.flush()
            logging.info("Setting Stockfish Ponder to %s", ponder)
        except Exception:
            logging.exception("Failed to set Ponder")

    # Custom options
    if "sf_options" in config:
        for option, value in config["sf_options"].items():
            # UCI wants true/false, Python formats a bool as True/False
            if isinstance(value, bool):
                value = "true" if value else "false"
            try:
                process.stdin.write(f"setoption name {option} value {value}\n")
                process.stdin.flush()
                logging.info("Setting custom option: %s = %s", option, value)
            except Exception:
                logging.exception("Failed to set custom option %s", option)

    # Verify ready
    try:
        process.stdin.write("isready\n")
        process.stdin.flush()
        wait_for_marker(output_queue, "readyok", timeout=5)
        logging.info("Stockfish initialization completed.")
    except Exception:
        logging.exception("Failed to verify readiness")


def run_remote_stockfish(config):
    """Start Stockfish through ssh and relay the GUI commands to it.

    The main thread reads the GUI commands on stdin and writes them to
    the ssh stdin; handle_output and handle_stderr run in daemon threads.
    Return on quit, end of stdin, Ctrl+C or a broken ssh pipe. Exit with
    status 1 if the ssh binary or the key file cannot be found.
    """
    # Basic checks
    ssh_bin = shutil.which("ssh")
    if not ssh_bin:
        logging.critical("ssh binary not found in PATH. Install OpenSSH or ensure ssh is available.")
        print("ssh binary not found in PATH. Install OpenSSH or ensure ssh is available.", file=sys.stderr)
        sys.exit(1)

    # Expand "~" first (on Windows Python uses USERPROFILE), then resolve a
    # relative path against the script directory
    key_file = os.path.expanduser(config.get("key_file", ""))
    if not os.path.isabs(key_file):
        key_file = os.path.join(os.path.dirname(sys.argv[0]) or ".", key_file)
    key_file = os.path.abspath(key_file)
    if not os.path.isfile(key_file):
        logging.critical("Key file not found: %s", key_file)
        print(f"Key file not found: {key_file}", file=sys.stderr)
        sys.exit(1)

    host = config["host"]
    username = config["username"]
    port = str(config.get("port", 22))
    remote_command = config.get("stockfish_command", "stockfish")

    # Build ssh command
    ssh_command = [
        ssh_bin,
        "-i", key_file,
        "-p", port,
        f"{username}@{host}",
        remote_command
    ]

    # Optionally append extra SSH options from config (list of strings)
    extra_opts = config.get("ssh_options", [])
    if extra_opts:
        # Insert after ssh binary, before -i
        ssh_command = [ssh_bin] + extra_opts + ssh_command[1:]

    logging.info("SSH command: %s", " ".join(ssh_command))

    try:
        process = subprocess.Popen(  # nosec B603 # argv list, no shell=True
            ssh_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        logging.info("SSH process started.")

        terminate_event = threading.Event()
        output_queue = queue.Queue()

        out_thread = threading.Thread(target=handle_output, args=(process, output_queue, terminate_event), daemon=True)
        err_thread = threading.Thread(target=handle_stderr, args=(process, terminate_event), daemon=True)
        out_thread.start()
        err_thread.start()

        # Auto-configure Stockfish before accepting user input
        configure_stockfish(process, config, output_queue)

        is_analyzing = False
        pending_command = None

        while True:
            try:
                user_input = input()
                logging.debug("User input: %r", user_input)

                if user_input.strip().lower() == "quit":
                    if process.poll() is None:
                        try:
                            process.stdin.write("quit\n")
                            process.stdin.flush()
                        except Exception:
                            pass
                    terminate_event.set()
                    break

                if is_analyzing and user_input.strip().lower() != "stop":
                    logging.info("Engine is analyzing. Sending 'stop' before next command.")
                    pending_command = user_input
                    try:
                        process.stdin.write("stop\n")
                        process.stdin.flush()
                    except Exception:
                        logging.exception("Failed to send stop")
                        pending_command = None
                    # wait for bestmove (with a reasonable timeout)
                    wait_for_marker(output_queue, "bestmove", timeout=10)
                    is_analyzing = False
                    continue

                # send user's command
                try:
                    process.stdin.write(user_input + "\n")
                    process.stdin.flush()
                except BrokenPipeError:
                    logging.error("Broken pipe writing to SSH process stdin.")
                    terminate_event.set()
                    break

                # update analyzing state
                cmd = user_input.strip().lower()
                if cmd.startswith("go infinite") or (cmd.startswith("go perft") and "infinite" in user_input):
                    is_analyzing = True
                elif cmd == "stop":
                    is_analyzing = False

                # specific waits
                if cmd == "uci":
                    wait_for_marker(output_queue, "uciok", timeout=5)
                elif cmd == "isready":
                    wait_for_marker(output_queue, "readyok", timeout=5)
                elif ((cmd == "go" or cmd.startswith("go "))
                      and "infinite" not in cmd):
                    wait_for_marker(output_queue, "bestmove", timeout=30)

                # process pending command if any
                if pending_command and not is_analyzing:
                    logging.info("Processing queued command: %r", pending_command)
                    try:
                        process.stdin.write(pending_command + "\n")
                        process.stdin.flush()
                    except Exception:
                        logging.exception("Failed to send pending command")
                    pending_command = None

            except EOFError:
                logging.warning("EOFError: stdin closed.")
                terminate_event.set()
                break
            except KeyboardInterrupt:
                logging.info("KeyboardInterrupt: exiting.")
                terminate_event.set()
                break
            except Exception:
                logging.exception("Unexpected error in main loop")

        # cleanup
        terminate_event.set()
        try:
            out_thread.join(timeout=2)
            err_thread.join(timeout=2)
        except Exception:
            pass
        if process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass
        logging.info("SSH wrapper terminated.")

    except Exception:
        logging.exception("Error running remote stockfish via ssh")
    finally:
        logging.info("Remote Stockfish wrapper finalizing.")


if __name__ == "__main__":
    cfg = load_config()
    setup_logging(cfg)
    logging.info("Starting remote Stockfish wrapper (native ssh).")
    run_remote_stockfish(cfg)
