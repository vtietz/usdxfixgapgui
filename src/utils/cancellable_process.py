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
    logger.debug("Running command: %s", ' '.join(command))
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    stdout, stderr = [], []

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
            process.kill()
            process.communicate()
            raise Exception("Process cancelled.")
        time.sleep(0.1)

    stdout_thread.join()
    stderr_thread.join()

    return process.returncode, ''.join(stdout), ''.join(stderr)