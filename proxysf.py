import subprocess
import threading
import sys
import os
import json
import logging
import queue
## Function to set up logging for the application
def setup_logging(config):
    """
    Configure logging for the application, only if logging is enabled in the config.

    Args:
        config (dict): Configuration dictionary loaded from config.json.
    """
    if config.get("logging_enabled", False):  # Check if logging is enabled in the configuration
        logging.basicConfig(
            filename="debug.log",  # Log file name
            level=logging.DEBUG,  # Log level (DEBUG includes detailed information)
            format="%(asctime)s - %(levelname)s - %(message)s"  # Format for log messages
        )
        logging.info("Logging initialized.")  # Log that logging has started
    else:
## If logging is disabled, suppress all log levels except CRITICAL
        logging.basicConfig(level=logging.CRITICAL)
## Function to load configuration from a JSON file
def load_config():
    """
    Load configuration from config.json located in the same directory as the script.

    Returns:
        dict: Loaded configuration data.
    """
    config_path = os.path.join(os.path.dirname(sys.argv[0]), "config.json")  # Get the config file path
    try:
        with open(config_path, "r") as file:  # Open the config file
            return json.load(file)  # Parse JSON and return as a dictionary
    except FileNotFoundError:
        logging.error(f"Configuration file '{config_path}' not found.")  # Log if the file is missing
        sys.exit(1)  # Exit the script with an error
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing configuration file: {e}")  # Log if JSON is malformed
        sys.exit(1)
## Function to handle output from Stockfish and log it
def handle_output(process, output_queue, terminate_event):
    """
    Continuously read output from Stockfish (via Plink) and write it to stdout and logs.

    Args:
        process: The subprocess running Stockfish (via Plink).
        output_queue: Queue to store output lines for sequential processing.
        terminate_event: Event to signal when to stop reading output.
    """
    try:
        while not terminate_event.is_set():  # Loop until termination signal is received
            output = process.stdout.readline()  # Read a line from Stockfish's stdout
            if not output:  # Stop if no output is received
                break
            output = output.strip()  # Remove extra whitespace from the output
            logging.debug(f"Stockfish output: {output}")  # Log the output
            output_queue.put(output)  # Add the output to the queue for processing
            sys.stdout.write(output + "\n")  # Print the output to the console
            sys.stdout.flush()  # Ensure it appears immediately
    except Exception as e:
        logging.error(f"Error reading Stockfish output: {e}")  # Log any errors
## Function to wait for a specific marker in the output queue
def wait_for_marker(output_queue, marker):
    """
    Wait for a specific marker in the output queue.

    Args:
        output_queue: Queue containing Stockfish output.
        marker: The marker to wait for.
    """
    try:
        while True:  # Continuously check for the marker
            output = output_queue.get()  # Get the next output line from the queue
            if marker in output:  # If the marker is found in the output
                logging.debug(f"Marker '{marker}' found in output.")  # Log that the marker was found
                break  # Exit the loop
    except Exception as e:
        logging.error(f"Error waiting for marker '{marker}': {e}")  # Log any errors
## Main function to run the remote Stockfish engine
def run_remote_stockfish(config):
    """
    Starts the remote Stockfish engine using plink and processes input sequentially.

    Args:
        config: Dictionary containing configuration parameters.
    """
## Build paths to plink and the key file
    plink_path = os.path.abspath(config["plink_path"])
    key_file_path = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), config["key_file"]))
    host = config["host"]
    username = config["username"]
    remote_command = config["stockfish_command"]
## Build the plink command to run Stockfish remotely
    plink_command = [
        plink_path,
        "-batch",  # Run in batch mode (non-interactive)
        "-ssh",  # Use SSH for connection
        "-i", key_file_path,  # Path to the private key file
        "-P 4242", # Destination port
        f"{username}@{host}",  # Remote username and host
        remote_command  # Command to run Stockfish on the remote server
    ]
    logging.info(f"Plink command: {' '.join(plink_command)}")  # Log the full command

    try:
## Start the plink process
        process = subprocess.Popen(
            plink_command,
            stdin=subprocess.PIPE,  # Input to the process
            stdout=subprocess.PIPE,  # Output from the process
            stderr=subprocess.PIPE,  # Error output from the process
            text=True,  # Use text mode for input/output
            bufsize=1  # Line buffering
        )
        logging.info("Plink process started successfully.")  # Log success
## Initialize synchronization tools
        terminate_event = threading.Event()  # Event to signal thread termination
        output_queue = queue.Queue()  # Queue to hold Stockfish output
## Track if Stockfish is analyzing a position
        is_analyzing = False
        pending_command = None  # To store a queued command
## Start a thread to handle Stockfish output
        output_thread = threading.Thread(target=handle_output, args=(process, output_queue, terminate_event))
        output_thread.daemon = True  # Run the thread in the background
        output_thread.start()
## Main loop to process user input
        while True:
            try:
                user_input = input()  # Read user input from the console
                logging.debug(f"User input: {user_input.strip()}")  # Log the input

                if user_input.strip().lower() == "quit":  # Check for quit command
                    process.stdin.write(user_input + "\n")
                    process.stdin.flush()
                    terminate_event.set()  # Stop the output thread
                    break

                if is_analyzing and user_input.strip().lower() != "stop":
## If the engine is analyzing, send "stop" before a new command
                    logging.info("Engine is analyzing. Sending 'stop' command.")
                    pending_command = user_input
                    process.stdin.write("stop\n")
                    process.stdin.flush()
                    wait_for_marker(output_queue, "bestmove")  # Wait for bestmove response
                    is_analyzing = False
                    continue
## Send the command to Stockfish
                process.stdin.write(user_input + "\n")
                process.stdin.flush()
## Update the analyzing state based on the command
                if user_input.strip().startswith("go infinite"):
                    is_analyzing = True
                elif user_input.strip().lower() == "stop":
                    is_analyzing = False
## Handle specific markers for commands
                if user_input.strip() == "uci":
                    wait_for_marker(output_queue, "uciok")
                elif user_input.strip() == "isready":
                    wait_for_marker(output_queue, "readyok")
                elif "go" in user_input and "infinite" not in user_input:
                    wait_for_marker(output_queue, "bestmove")
## Process any pending command after "stop"
                if pending_command and not is_analyzing:
                    logging.info(f"Processing queued command: {pending_command.strip()}")
                    process.stdin.write(pending_command + "\n")
                    process.stdin.flush()
                    pending_command = None

            except EOFError:  # Handle end-of-file (e.g., when stdin closes)
                logging.warning("EOFError: stdin closed unexpectedly.")
                terminate_event.set()
                break
            except KeyboardInterrupt:  # Handle Ctrl+C
                logging.info("KeyboardInterrupt: Exiting...")
                terminate_event.set()
                break
            except Exception as e:  # Catch unexpected errors
                logging.error(f"Error processing user input: {e}")
## Wait for the output thread to finish
        output_thread.join()
## Terminate the plink process
        process.terminate()
        logging.info("Plink process terminated.")

    except Exception as e:
        logging.error(f"Error running Stockfish with Plink: {e}")  # Log any errors
    finally:
        logging.info("Remote Stockfish wrapper terminated.")  # Final cleanup log
## Main script entry point
if __name__ == "__main__":
    config = load_config()  # Load configuration
    setup_logging(config)  # Initialize logging
    logging.info("Starting remote Stockfish wrapper.")  # Log startup message
    run_remote_stockfish(config)  # Run the main function
