import subprocess
import threading
import sys
import os
import json
import logging
import queue
import shutil
import time

def setup_logging(config):
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
    try:
        while not terminate_event.is_set():
            line = process.stdout.readline()
            if line == "":
                # EOF reached
                break
            line = line.rstrip("\r\n")
            logging.debug(f"STDOUT: {line}")
            output_queue.put(line)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
    except Exception as e:
        logging.exception(f"Error reading stdout: {e}")

def handle_stderr(process, terminate_event):
    try:
        while not terminate_event.is_set():
            line = process.stderr.readline()
            if line == "":
                break
            line = line.rstrip("\r\n")
            logging.warning(f"STDERR: {line}")
    except Exception as e:
        logging.exception(f"Error reading stderr: {e}")

def wait_for_marker(output_queue, marker, timeout=None):
    start = time.time()
    try:
        while True:
            try:
                output = output_queue.get(timeout=0.5)
            except queue.Empty:
                if timeout is not None and (time.time() - start) > timeout:
                    logging.error(f"Timeout waiting for marker '{marker}'")
                    return False
                continue
            if marker in output:
                logging.debug(f"Marker '{marker}' found.")
                return True
    except Exception as e:
        logging.exception(f"Error in wait_for_marker: {e}")
        return False

def configure_stockfish(process, config, output_queue):
    """Configure Stockfish with optimal settings from config.json"""
    logging.info("Initializing Stockfish with custom configuration...")
    
    # Send uci first
    try:
        process.stdin.write("uci\n")
        process.stdin.flush()
        wait_for_marker(output_queue, "uciok", timeout=5)
    except Exception as e:
        logging.exception(f"Failed to initialize UCI: {e}")
        return
    
    # Configure threads
    if "sf_threads" in config:
        threads = config["sf_threads"]
        try:
            process.stdin.write(f"setoption name Threads value {threads}\n")
            process.stdin.flush()
            logging.info(f"Setting Stockfish threads to {threads}")
        except Exception as e:
            logging.exception(f"Failed to set threads: {e}")
    
    # Configure hash
    if "sf_hash" in config:
        hash_mb = config["sf_hash"]
        try:
            process.stdin.write(f"setoption name Hash value {hash_mb}\n")
            process.stdin.flush()
            logging.info(f"Setting Stockfish hash to {hash_mb}MB")
        except Exception as e:
            logging.exception(f"Failed to set hash: {e}")
    
    # Configure MultiPV
    if "sf_multipv" in config:
        multipv = config["sf_multipv"]
        try:
            process.stdin.write(f"setoption name MultiPV value {multipv}\n")
            process.stdin.flush()
            logging.info(f"Setting Stockfish MultiPV to {multipv}")
        except Exception as e:
            logging.exception(f"Failed to set MultiPV: {e}")
    
    # Configure Ponder
    if "sf_ponder" in config:
        ponder = "true" if config["sf_ponder"] else "false"
        try:
            process.stdin.write(f"setoption name Ponder value {ponder}\n")
            process.stdin.flush()
            logging.info(f"Setting Stockfish Ponder to {ponder}")
        except Exception as e:
            logging.exception(f"Failed to set Ponder: {e}")
    
    # Custom options
    if "sf_options" in config:
        for option, value in config["sf_options"].items():
            try:
                process.stdin.write(f"setoption name {option} value {value}\n")
                process.stdin.flush()
                logging.info(f"Setting custom option: {option} = {value}")
            except Exception as e:
                logging.exception(f"Failed to set custom option {option}: {e}")
    
    # Verify ready
    try:
        process.stdin.write("isready\n")
        process.stdin.flush()
        wait_for_marker(output_queue, "readyok", timeout=5)
        logging.info("Stockfish initialization completed.")
    except Exception as e:
        logging.exception(f"Failed to verify readiness: {e}")

def run_remote_stockfish(config):
    # Basic checks
    ssh_bin = shutil.which("ssh")
    if not ssh_bin:
        logging.critical("ssh binary not found in PATH. Install OpenSSH or ensure ssh is available.")
        print("ssh binary not found in PATH. Install OpenSSH or ensure ssh is available.", file=sys.stderr)
        sys.exit(1)

    # Expand "~" first (on Windows Python uses USERPROFILE), then resolve a
    # relative path against the script directory, as before
    key_file = os.path.expanduser(config.get("key_file", ""))
    if not os.path.isabs(key_file):
        key_file = os.path.join(os.path.dirname(sys.argv[0]) or ".", key_file)
    key_file = os.path.abspath(key_file)
    if not os.path.isfile(key_file):
        logging.critical(f"Key file not found: {key_file}")
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

    logging.info(f"SSH command: {' '.join(ssh_command)}")

    try:
        process = subprocess.Popen(
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
                logging.debug(f"User input: {user_input!r}")

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
                    except Exception as e:
                        logging.exception(f"Failed to send stop: {e}")
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

                # update analyzing state (FIX: clarified logic with parentheses)
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
                elif "go" in cmd and "infinite" not in cmd:
                    wait_for_marker(output_queue, "bestmove", timeout=30)

                # process pending command if any
                if pending_command and not is_analyzing:
                    logging.info(f"Processing queued command: {pending_command!r}")
                    try:
                        process.stdin.write(pending_command + "\n")
                        process.stdin.flush()
                    except Exception as e:
                        logging.exception(f"Failed to send pending command: {e}")
                    pending_command = None

            except EOFError:
                logging.warning("EOFError: stdin closed.")
                terminate_event.set()
                break
            except KeyboardInterrupt:
                logging.info("KeyboardInterrupt: exiting.")
                terminate_event.set()
                break
            except Exception as e:
                logging.exception(f"Unexpected error in main loop: {e}")

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

    except Exception as e:
        logging.exception(f"Error running remote stockfish via ssh: {e}")
    finally:
        logging.info("Remote Stockfish wrapper finalizing.")

if __name__ == "__main__":
    cfg = load_config()
    setup_logging(cfg)
    logging.info("Starting remote Stockfish wrapper (native ssh).")
    run_remote_stockfish(cfg)
