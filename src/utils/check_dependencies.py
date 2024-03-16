import logging
import subprocess

logger = logging.getLogger(__name__)

def check_dependency(command, version_flag='--version'):
    """
    Checks if a given command-line tool is installed and accessible.

    Parameters:
    - command: The command to check (e.g., 'ffmpeg').
    - version_flag: The flag used to request the tool's version (default is '--version').

    Returns:
    - True if the tool is found and the command executes successfully.
    - False otherwise.
    """
    try:
        # Execute the command with the version flag, capture the output.
        result = subprocess.run([command, version_flag], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            logger.debug(f"{command} found: {result.stdout.splitlines()[0]}")
            return True
        else:
            logger.debug(f"{command} found, but error encountered: {result.stderr}")
            return True
    except FileNotFoundError:
        return False

def check_dependencies(dependencies):
    """
    Checks if the given dependencies are installed and accessible.

    Parameters:
    - dependencies: A list of tuples, where each tuple contains:
        - command: The command to check (e.g., 'ffmpeg').
        - version_flag: The flag used to request the tool's version (default is '--version').

    Returns:
    - True if all dependencies are found and the commands execute successfully.
    - False otherwise.
    """
    all_dependencies_met = True
    for command, version_flag in dependencies:
        if not check_dependency(command, version_flag):
            logger.error(f"Dependency {command} not found.")
            all_dependencies_met = False
    return all_dependencies_met

