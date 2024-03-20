import logging
import time
import subprocess
import threading

logger = logging.getLogger(__name__)

def read_output(stream, collector):
    """Read subprocess output in a thread and collect lines."""
    try:
        while True:
            line = stream.readline()
            if not line:  # If line is empty, end of file is reached
                break
            collector.append(line.decode('utf-8', errors='ignore'))
    finally:
        stream.close()

def run_cancellable_process(command, check_cancellation=None):
    logger.debug(f"Running process: {command}")
    # Initialize the subprocess with text=True to handle output as strings
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1)

    # Lists to collect output and error lines
    stdout, stderr = [], []

    # Create threads to read stdout and stderr without blocking
    stdout_thread = threading.Thread(target=read_output, args=(process.stdout, stdout))
    stderr_thread = threading.Thread(target=read_output, args=(process.stderr, stderr))
    stdout_thread.start()
    stderr_thread.start()

    while True:
        if process.poll() is not None:  # Check if process has terminated
            break  # Process is done, exit the loop

        if check_cancellation and check_cancellation():
            process.kill()  # Kill the process if cancellation is requested
            process.communicate()  # Ensure resources are cleaned up
            raise Exception("Process cancelled.")

        # Sleep briefly to reduce CPU usage in the loop
        time.sleep(0.1)

    # Wait for the output threads to finish
    stdout_thread.join()
    stderr_thread.join()

    return process.returncode, ''.join(stdout), ''.join(stderr)
