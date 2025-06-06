import logging
import time
import subprocess
import threading
import platform  # Import platform module to detect the OS

logger = logging.getLogger(__name__)

def run_cancellable_process(command, check_cancellation=None):
    logger.debug("Running command: %s", ' '.join(command))
    
    # Set up the process creation parameters
    popen_kwargs = {
        'stdout': subprocess.PIPE,
        'stderr': subprocess.PIPE,
        'text': True,
        'encoding': 'utf-8',  # Specify UTF-8 encoding
        'errors': 'ignore'    # Ignore decoding errors
    }
    
    # Only add creationflags on Windows
    if platform.system() == 'Windows':
        popen_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW  # Suppress cmd window
    
    # Create the process with the appropriate arguments
    process = subprocess.Popen(command, **popen_kwargs)

    stdout, stderr = [], []

    # This function now reads already decoded strings
    def read_output(pipe, output_list):
        for line in pipe:
            output_list.append(line)
            logger.debug(line.strip())

    stdout_thread = threading.Thread(target=read_output, args=(process.stdout, stdout))
    stderr_thread = threading.Thread(target=read_output, args=(process.stderr, stderr))
    stdout_thread.start()
    stderr_thread.start()

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

    stdout_thread.join()
    stderr_thread.join()

    return process.returncode, ''.join(stdout), ''.join(stderr)