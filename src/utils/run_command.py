import subprocess
import sys

def run_command(command, show_output=True):
    """Run a command using subprocess and return the output."""
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if show_output:
      if result.stdout.strip():
          print(result.stdout)
      if result.stderr.strip():
          print(result.stderr, file=sys.stderr)
    return result.stdout, result.stderr
