import hashlib
import os
import sys
import logging

from common.constants import APP_IGNORE_FILENAME, APP_INFO_FILENAME

IGNORE_FILE = APP_IGNORE_FILENAME
INFO_FILE = APP_INFO_FILENAME
WAVEFORM_FILE = "waveform.png"


logger = logging.getLogger(__name__)


def get_relative_path(root, path):
    return os.path.relpath(path, root)


def find_txt_file(path):
    """
    Finds a .txt file in the given path.
    If path is a directory, returns the first .txt file found in it.
    If path is a .txt file, returns the path itself.
    Otherwise, returns the path as is (it might be assumed to be a txt file path).

    Args:
        path: A directory path or file path

    Returns:
        Path to a .txt file or the original path
    """
    if os.path.isdir(path):
        # If path is a directory, find the .txt file
        for file in os.listdir(path):
            if file.endswith(".txt"):
                return os.path.join(path, file)
        # No .txt file found
        return None
    elif path.endswith(".txt"):
        # If path is already the txt file
        return path
    else:
        # If path is not a directory or a txt file
        # it might be the directory path or txt file path without extension
        return path


def is_portable_mode():
    """
    Detect if running in portable mode (directory build vs one-file exe).

    Portable mode = PyInstaller directory build with _internal folder alongside exe.
    One-file mode = PyInstaller one-file exe that extracts to temp.

    Returns:
        bool: True if portable mode, False otherwise
    """
    if not getattr(sys, "frozen", False):
        # Not frozen = running as script = use system directories
        return False

    app_dir = os.path.dirname(sys.executable)
    # Check for _internal directory (PyInstaller directory build marker)
    internal_dir = os.path.join(app_dir, "_internal")
    return os.path.isdir(internal_dir)


def get_localappdata_dir():
    """
    Get platform-appropriate application data directory for USDX FixGap.

    This is the recommended location for all user data (config, cache, models, etc.).
    Follows platform conventions and respects XDG Base Directory Specification on Linux.

    Returns:
        str: Path to application data directory

    Platform paths:
        Windows: %LOCALAPPDATA%/USDXFixGap/
        Linux:   ~/.local/share/USDXFixGap/ (respects XDG_DATA_HOME)
        macOS:   ~/Library/Application Support/USDXFixGap/
        Portable: <app_directory>/ (when _internal folder detected)
    """
    # Portable mode: Store data alongside executable
    if is_portable_mode():
        app_dir = get_app_dir()
        logger.info(f"Portable mode detected, using app directory: {app_dir}")
        return app_dir

    from common.constants import APP_FOLDER_NAME

    # Windows: Use LOCALAPPDATA
    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            app_data_dir = os.path.join(local_app_data, APP_FOLDER_NAME)
            os.makedirs(app_data_dir, exist_ok=True)
            return app_data_dir
        # Windows portable mode fallback
        logger.warning("LOCALAPPDATA not found, using app directory (portable mode)")
        return get_app_dir()

    # macOS: Use Application Support
    elif sys.platform == "darwin":
        app_support = os.path.expanduser(f"~/Library/Application Support/{APP_FOLDER_NAME}")
        os.makedirs(app_support, exist_ok=True)
        return app_support

    # Linux and other Unix-like: Use XDG standard
    else:
        # Respect XDG_DATA_HOME if set, otherwise use default ~/.local/share
        xdg_data = os.getenv("XDG_DATA_HOME")
        if xdg_data:
            app_data_dir = os.path.join(xdg_data, APP_FOLDER_NAME)
        else:
            app_data_dir = os.path.expanduser(f"~/.local/share/{APP_FOLDER_NAME}")
        os.makedirs(app_data_dir, exist_ok=True)
        return app_data_dir


def get_app_dir():
    """
    Get the directory of the executable or script.

    Note: For user data storage, prefer get_localappdata_dir() instead.
    This function is mainly for resource loading and portable mode fallback.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        # Running in a PyInstaller bundle
        return os.path.dirname(sys.executable)
    # Running as a script
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_models_dir(config=None):
    """
    Get the directory for AI models (Demucs, Spleeter, etc.).

    Can be configured via Config.models_directory or defaults to LOCALAPPDATA.

    Args:
        config: Optional Config object with custom models_directory setting

    Returns:
        str: Path to models directory

    Examples:
        Default: C:/Users/<username>/AppData/Local/USDXFixGap/models/
        Custom: E:/USDXFixGap/models/ (if configured)
        Network: //server/shared/USDXFixGap/models/ (if configured)
    """
    if config and hasattr(config, "models_directory") and config.models_directory:
        models_dir = os.path.expandvars(config.models_directory)
    else:
        models_dir = os.path.join(get_localappdata_dir(), "models")

    os.makedirs(models_dir, exist_ok=True)
    return models_dir


def get_demucs_models_dir(config=None):
    """Get directory for Demucs models."""
    return os.path.join(get_models_dir(config), "demucs")


def get_spleeter_models_dir(config=None):
    """Get directory for Spleeter models."""
    return os.path.join(get_models_dir(config), "spleeter")


def resource_path(relative_path):
    """Get the absolute path to a resource, works for dev and PyInstaller."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        # Running in a PyInstaller bundle
        return os.path.join(meipass, relative_path)

    # Check in the application directory first
    app_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    app_path = os.path.join(app_dir, relative_path)
    if os.path.exists(app_path):
        return app_path

    # Otherwise check in the current directory
    return os.path.join(os.path.abspath("."), relative_path)


def get_song_path(txt_file):
    return os.path.dirname(txt_file)


def get_tmp_path(tmp_dir, audio_file):
    return os.path.join(tmp_dir, os.path.splitext(os.path.basename(audio_file))[0])


def get_vocals_path(tmp_path, max_detection_time=None):
    if max_detection_time is None:
        return os.path.join(tmp_path, "vocals.mp3")
    return os.path.join(tmp_path, f"vocals_{max_detection_time}.mp3")


def get_info_file_path(song_path):
    return os.path.join(song_path, INFO_FILE)


def get_txt_path(info_file):
    path = os.path.dirname(info_file)
    return os.path.join(path, f"{os.path.basename(info_file).replace(INFO_FILE, '.txt')}")


def get_waveform_path(tmp_path, type=None, length=None, extension="png"):
    file_name = "waveform"
    if type in ["audio", "vocals"]:
        file_name += f"_{type}"
    if length:
        file_name += f"_{length}"
    file_name += f".{extension}"
    return os.path.join(tmp_path, file_name)


def list_files(directory, endswith=".txt"):
    """List all .txt files in the directory and its subdirectories."""
    txt_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(endswith):
                txt_files.append(os.path.join(root, file))
    return txt_files


def ignore_file_exists(txt_file):
    ignre_file = os.path.join(os.path.dirname(txt_file), IGNORE_FILE)
    return os.path.exists(ignre_file)


def delete_folder(folder):
    """Delete the given folder and its contents."""
    if not os.path.exists(folder):
        return
    logger.debug(f"Deleting {folder}...")
    try:
        for root, dirs, files in os.walk(folder, topdown=False):
            for file in files:
                os.remove(os.path.join(root, file))
            for dir in dirs:
                os.rmdir(os.path.join(root, dir))
        os.rmdir(folder)
    except Exception as e:
        logger.error(f"Error deleting {folder}: {e}")


def generate_directory_hash(directory_path):
    """
    Generates a hash value from a directory path using SHA-256. This method provides a consistent hash value
    across different runs of the application.

    :param directory_path: The path of the directory to hash.
    :return: A hexadecimal hash value as a string.
    """
    # Encode the directory path to a byte representation required by hashlib
    directory_bytes = directory_path.encode("utf-8")
    # Use SHA-256 from hashlib and compute the hash
    hash_object = hashlib.sha256(directory_bytes)
    # Get the hexadecimal representation of the hash
    hex_hash = hash_object.hexdigest()
    short_hash = hex_hash[:8]  # take the first 8 characters for brevity
    return short_hash


def move_file(source, destination, overwrite=False):
    """
    Moves a file from source to destination.
    If overwrite is True and the destination file exists, it will be removed before moving.
    """
    # Check if the destination file exists and if overwrite is enabled
    if os.path.exists(destination) and overwrite:
        os.remove(destination)

    # Ensure the destination directory exists
    os.makedirs(os.path.dirname(destination), exist_ok=True)

    # Move the file
    os.rename(source, destination)


def rmtree(directory):
    """Recursively remove the directory and its contents."""
    if not os.path.exists(directory):
        return
    logger.debug(f"Removing directory {directory}")
    try:
        for root, dirs, files in os.walk(directory, topdown=False):
            for file in files:
                os.remove(os.path.join(root, file))
            for dir in dirs:
                os.rmdir(os.path.join(root, dir))
        os.rmdir(directory)
    except Exception as e:
        logger.error(f"Error removing directory {directory}: {e}")


def get_file_checksum(file_path, algorithm="sha256", buffer_size=65536):
    """
    Calculate the checksum of a file using the specified algorithm.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use ('md5', 'sha1', 'sha256', etc.)
        buffer_size: Size of chunks to read at a time

    Returns:
        String containing the hexadecimal digest of the file
    """
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        logger.error(f"File not found or not accessible: {file_path}")
        return None

    try:
        hash_algo = getattr(hashlib, algorithm.lower())()

        with open(file_path, "rb") as f:
            # Read the file in chunks to handle large files efficiently
            while chunk := f.read(buffer_size):
                hash_algo.update(chunk)

        return hash_algo.hexdigest()
    except (IOError, OSError) as e:
        logger.error(f"Error calculating checksum for {file_path}: {e}")
        return None
    except AttributeError:
        logger.error(f"Hash algorithm not available: {algorithm}")
        return None
