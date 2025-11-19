import logging
import time
import subprocess
import threading
import platform  # Import platform module to detect the OS
import shutil  # For checking command availability

logger = logging.getLogger(__name__)


def run_cancellable_process(command, check_cancellation=None):
    """Run an external process that can be cancelled.

    Provides a clearer error message when the underlying executable is not
    found (e.g. 'ffmpeg'), which otherwise results in a confusing
    FileNotFoundError that might be mistaken for a missing audio file.

    Returns:
        tuple: (returncode, stdout, stderr)

    Raises:
        FileNotFoundError: If executable is not found
        Exception: If process is cancelled or fails with non-zero exit code
        OSError: If process creation or execution fails
    """
    logger.debug("Running command: %s", " ".join(command))

    if not command or not isinstance(command, (list, tuple)):
        raise ValueError("command must be a non-empty list/tuple")

    exe = command[0]
    # On Windows, PATHEXT allows running without extension, shutil.which handles that.
    if shutil.which(exe) is None:
        raise FileNotFoundError(f"Executable not found: '{exe}'. Is the dependency installed and on PATH?")

    # Set up the process creation parameters
    popen_kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",  # Specify UTF-8 encoding
        "errors": "ignore",  # Ignore decoding errors
    }

    # Only add creationflags on Windows
    if platform.system() == "Windows":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # Suppress cmd window

    process = None
    stdout, stderr = [], []

    try:
        # Create the process with the appropriate arguments
        process = subprocess.Popen(command, **popen_kwargs)
    except OSError as e:
        # Handle OS-level errors (permission denied, etc.)
        logger.error(f"Failed to create process for '{exe}': {e}")
        raise OSError(f"Failed to start '{exe}': {e}") from e
    except Exception as e:
        # Catch any other unexpected errors during process creation
        logger.error(f"Unexpected error creating process for '{exe}': {e}")
        raise

    # This function now reads already decoded strings
    def read_output(pipe, output_list):
        try:
            for line in pipe:
                output_list.append(line)
                logger.debug(line.strip())
        except Exception as e:
            logger.warning(f"Error reading process output: {e}")

    stdout_thread = threading.Thread(target=read_output, args=(process.stdout, stdout), daemon=True)
    stderr_thread = threading.Thread(target=read_output, args=(process.stderr, stderr), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    try:
        while True:
            if process.poll() is not None:
                break
            if check_cancellation and check_cancellation():
                logger.info("Cancellation requested, terminating process.")
                process.kill()
                # Wait briefly for threads to potentially finish reading after kill
                stdout_thread.join(timeout=0.5)
                stderr_thread.join(timeout=0.5)
                # Ensure streams are closed if threads are still alive
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
                # Wait for process termination
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    logger.warning("Process did not terminate gracefully after kill.")
                raise Exception("Process cancelled.")
            time.sleep(0.1)

        stdout_thread.join(timeout=2.0)
        stderr_thread.join(timeout=2.0)

    except Exception:
        # Ensure process cleanup on any error
        if process and process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=1.0)
            except Exception:
                pass
        raise
    finally:
        # Always close streams
        if process:
            if process.stdout:
                try:
                    process.stdout.close()
                except Exception:
                    pass
            if process.stderr:
                try:
                    process.stderr.close()
                except Exception:
                    pass

    return process.returncode, "".join(stdout), "".join(stderr)
