import os
import configparser
import logging
from PySide6.QtCore import QObject
from utils.files import get_localappdata_dir, is_portable_mode, get_app_dir

logger = logging.getLogger(__name__)


class Config(QObject):
    def __init__(self, custom_config_path: str | None = None):
        """Initialize Config from file.

        Args:
            custom_config_path: Optional path to custom config file.
                               Useful for testing different parameter sets.
                               If None, uses system config location.
        """
        super().__init__()

        # Determine config path
        if custom_config_path:
            self.config_path = custom_config_path
            logger.debug(f"Using custom config: {self.config_path}")
        else:
            # Check if running in test mode (pytest sets PYTEST_CURRENT_TEST)
            # In test mode, use temp config to avoid polluting user's real config
            if "PYTEST_CURRENT_TEST" in os.environ:
                import tempfile

                test_config_dir = os.path.join(tempfile.gettempdir(), "usdxfixgap_test")
                os.makedirs(test_config_dir, exist_ok=True)
                self.config_path = os.path.join(test_config_dir, "config.ini")
                logger.debug(f"Test mode detected, using temp config: {self.config_path}")
            else:
                self.config_path = os.path.join(get_localappdata_dir(), "config.ini")

        config_exists = os.path.exists(self.config_path)

        if config_exists:
            # Existing config: Load without injecting defaults
            logger.debug(f"Loading existing config from: {self.config_path}")
            self._config = configparser.ConfigParser()
            self._config.read(self.config_path)
        else:
            # New config: Create with defaults
            logger.info(f"Config file not found. Creating default config at: {self.config_path}")
            self._config = configparser.ConfigParser()
            self._set_defaults()

            # Write the default config file
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as configfile:
                self._config.write(configfile)
            logger.info("Default config.ini created successfully")

        # Initialize properties from config values (using fallbacks for missing keys)
        self._initialize_properties()

    def ensure_config_file_exists(self):
        """
        DEPRECATED: Config file existence is now handled in __init__.
        This method remains for backward compatibility but does nothing.
        """
        return self.config_path

    def _get_defaults(self):
        """Get default configuration values as a dictionary structure."""
        localappdata = get_localappdata_dir()
        return {
            "Paths": {
                "tmp_root": os.path.join(localappdata, ".tmp"),
                "default_directory": os.path.join(localappdata, "samples"),
                "last_directory": "",
                "models_directory": "",
            },
            "Detection": {
                "default_detection_time": 30,
                "gap_tolerance": 500,
                "vocal_start_window_sec": 20,
                "vocal_window_increment_sec": 10,
                "vocal_window_max_sec": 60,
            },
            "Colors": {
                "detected_gap_color": "blue",
                "playback_position_color": "red",
                "waveform_color": "gray",
                "silence_periods_color": "105,105,105,128",
            },
            "Player": {"adjust_player_position_step_audio": 100, "adjust_player_position_step_vocals": 10},
            "Processing": {"method": "mdx", "normalization_level": -20, "auto_normalize": False},
            "mdx": {
                "chunk_duration_ms": 12000,
                "chunk_overlap_ms": 6000,
                "frame_duration_ms": 25,
                "hop_duration_ms": 20,
                "noise_floor_duration_ms": 1200,
                "onset_snr_threshold": 4.5,
                "onset_abs_threshold": 0.012,
                "min_voiced_duration_ms": 150,
                "hysteresis_ms": 350,
                "initial_radius_ms": 7500,
                "radius_increment_ms": 7500,
                "max_expansions": 3,
                "use_fp16": False,
                "resample_hz": 0,
                "early_stop_tolerance_ms": 500,
                "tf32": True,
                "confidence_threshold": 0.55,
                "preview_pre_ms": 3000,
                "preview_post_ms": 9000,
            },
            "General": {
                "log_level": "INFO",
                "gpu_opt_in": False,
                "gpu_flavor": "cu121",
                "gpu_pack_installed_version": "",
                "gpu_pack_path": "",
                "gpu_last_health": "",
                "gpu_last_error": "",
                "gpu_pack_dialog_dont_show": False,
                "gpu_pack_dont_ask": False,
                "splash_dont_show_health": False,
                "prefer_system_pytorch": False,
                "song_list_batch_size": 25,
            },
            "Audio": {"default_volume": 0.5, "auto_play": False},
            "Window": {
                "width": 1024,
                "height": 768,
                "x": -1,
                "y": -1,
                "maximized": False,
                "main_splitter_pos": "2,1",
                "second_splitter_pos": "1,1",
            },
            "WatchMode": {
                "watch_mode_default": False,
                "watch_debounce_ms": 500,
                "watch_ignore_patterns": ".tmp,~,.crdownload,.part",
            },
        }

    def _set_defaults(self):
        """Set default configuration values in the ConfigParser object."""
        defaults = self._get_defaults()

        for section, values in defaults.items():
            self._config[section] = {}
            for key, value in values.items():
                # Convert all values to strings for ConfigParser
                if isinstance(value, bool):
                    self._config[section][key] = "true" if value else "false"
                else:
                    self._config[section][key] = str(value)

    def _make_path_portable(self, path: str) -> str:
        """Convert absolute path to relative path in portable mode.

        Args:
            path: Absolute path or empty string

        Returns:
            Relative path if in portable mode and path is under app_dir, otherwise absolute path
        """
        if not path or not is_portable_mode():
            return path

        app_dir = get_app_dir()
        abs_path = os.path.abspath(path)

        # If path is under app_dir, make it relative
        try:
            rel_path = os.path.relpath(abs_path, app_dir)
            # Check if it's actually relative (doesn't start with ..)
            if not rel_path.startswith(".."):
                logger.debug(f"Portable mode: Converting '{abs_path}' → './{rel_path}'")
                return f"./{rel_path}"
        except (ValueError, OSError):
            # Different drives on Windows or other issues
            pass

        return path

    def _resolve_path_from_config(self, path: str) -> str:
        """Resolve path loaded from config (may be relative in portable mode).

        Args:
            path: Path from config file (may be relative like ./models)

        Returns:
            Absolute path
        """
        if not path:
            return path

        # If path starts with ./ or .\\ it's relative to app dir in portable mode
        if path.startswith("./") or path.startswith(".\\"):
            if is_portable_mode():
                app_dir = get_app_dir()
                abs_path = os.path.abspath(os.path.join(app_dir, path[2:]))
                logger.debug(f"Portable mode: Resolving '{path}' → '{abs_path}'")
                return abs_path

        return path

    def _initialize_properties(self):
        """Initialize class properties from config values with fallbacks."""
        defaults = self._get_defaults()

        # Paths (resolve relative paths in portable mode)
        self.tmp_root = self._config.get("Paths", "tmp_root", fallback=defaults["Paths"]["tmp_root"])
        self.default_directory = self._config.get(
            "Paths", "default_directory", fallback=defaults["Paths"]["default_directory"]
        )
        self.last_directory = self._resolve_path_from_config(
            self._config.get("Paths", "last_directory", fallback=defaults["Paths"]["last_directory"])
        )
        self.models_directory = self._config.get(
            "Paths", "models_directory", fallback=defaults["Paths"]["models_directory"]
        )

        # Detection
        self.default_detection_time = self._config.getint(
            "Detection", "default_detection_time", fallback=defaults["Detection"]["default_detection_time"]
        )
        self.gap_tolerance = self._config.getint(
            "Detection", "gap_tolerance", fallback=defaults["Detection"]["gap_tolerance"]
        )
        self.vocal_start_window_sec = self._config.getint(
            "Detection", "vocal_start_window_sec", fallback=defaults["Detection"]["vocal_start_window_sec"]
        )
        self.vocal_window_increment_sec = self._config.getint(
            "Detection", "vocal_window_increment_sec", fallback=defaults["Detection"]["vocal_window_increment_sec"]
        )
        self.vocal_window_max_sec = self._config.getint(
            "Detection", "vocal_window_max_sec", fallback=defaults["Detection"]["vocal_window_max_sec"]
        )

        # Colors
        self.detected_gap_color = self._config.get(
            "Colors", "detected_gap_color", fallback=defaults["Colors"]["detected_gap_color"]
        )
        self.playback_position_color = self._config.get(
            "Colors", "playback_position_color", fallback=defaults["Colors"]["playback_position_color"]
        )
        self.waveform_color = self._config.get(
            "Colors", "waveform_color", fallback=defaults["Colors"]["waveform_color"]
        )

        # Parse the RGBA tuple
        rgba_str = self._config.get(
            "Colors", "silence_periods_color", fallback=defaults["Colors"]["silence_periods_color"]
        )
        rgba_values = [int(x.strip()) for x in rgba_str.split(",")]
        self.silence_periods_color = tuple(rgba_values)

        # Player
        self.adjust_player_position_step_audio = self._config.getint(
            "Player",
            "adjust_player_position_step_audio",
            fallback=defaults["Player"]["adjust_player_position_step_audio"],
        )
        self.adjust_player_position_step_vocals = self._config.getint(
            "Player",
            "adjust_player_position_step_vocals",
            fallback=defaults["Player"]["adjust_player_position_step_vocals"],
        )

        # Processing
        self.method = self._config.get("Processing", "method", fallback=defaults["Processing"]["method"])
        self.normalization_level = self._config.getint(
            "Processing", "normalization_level", fallback=defaults["Processing"]["normalization_level"]
        )
        self.auto_normalize = self._config.getboolean(
            "Processing", "auto_normalize", fallback=defaults["Processing"]["auto_normalize"]
        )

        # MDX settings (all with fallbacks)
        mdx_defaults = defaults["mdx"]
        self.mdx_chunk_duration_ms = self._config.getint(
            "mdx", "chunk_duration_ms", fallback=mdx_defaults["chunk_duration_ms"]
        )
        self.mdx_chunk_overlap_ms = self._config.getint(
            "mdx", "chunk_overlap_ms", fallback=mdx_defaults["chunk_overlap_ms"]
        )
        self.mdx_frame_duration_ms = self._config.getint(
            "mdx", "frame_duration_ms", fallback=mdx_defaults["frame_duration_ms"]
        )
        self.mdx_hop_duration_ms = self._config.getint(
            "mdx", "hop_duration_ms", fallback=mdx_defaults["hop_duration_ms"]
        )
        self.mdx_noise_floor_duration_ms = self._config.getint(
            "mdx", "noise_floor_duration_ms", fallback=mdx_defaults["noise_floor_duration_ms"]
        )
        self.mdx_onset_snr_threshold = self._config.getfloat(
            "mdx", "onset_snr_threshold", fallback=mdx_defaults["onset_snr_threshold"]
        )
        self.mdx_onset_abs_threshold = self._config.getfloat(
            "mdx", "onset_abs_threshold", fallback=mdx_defaults["onset_abs_threshold"]
        )
        self.mdx_min_voiced_duration_ms = self._config.getint(
            "mdx", "min_voiced_duration_ms", fallback=mdx_defaults["min_voiced_duration_ms"]
        )
        self.mdx_hysteresis_ms = self._config.getint("mdx", "hysteresis_ms", fallback=mdx_defaults["hysteresis_ms"])
        # Expanding search parameters
        self.mdx_initial_radius_ms = self._config.getint(
            "mdx", "initial_radius_ms", fallback=mdx_defaults["initial_radius_ms"]
        )
        self.mdx_radius_increment_ms = self._config.getint(
            "mdx", "radius_increment_ms", fallback=mdx_defaults["radius_increment_ms"]
        )
        self.mdx_max_expansions = self._config.getint("mdx", "max_expansions", fallback=mdx_defaults["max_expansions"])
        # Performance optimizations
        self.mdx_use_fp16 = self._config.getboolean("mdx", "use_fp16", fallback=mdx_defaults["use_fp16"])
        self.mdx_resample_hz = self._config.getint("mdx", "resample_hz", fallback=mdx_defaults["resample_hz"])
        self.mdx_early_stop_tolerance_ms = self._config.getint(
            "mdx", "early_stop_tolerance_ms", fallback=mdx_defaults["early_stop_tolerance_ms"]
        )
        self.mdx_tf32 = self._config.getboolean("mdx", "tf32", fallback=mdx_defaults["tf32"])
        # Confidence and preview
        self.mdx_confidence_threshold = self._config.getfloat(
            "mdx", "confidence_threshold", fallback=mdx_defaults["confidence_threshold"]
        )
        self.mdx_preview_pre_ms = self._config.getint("mdx", "preview_pre_ms", fallback=mdx_defaults["preview_pre_ms"])
        self.mdx_preview_post_ms = self._config.getint(
            "mdx", "preview_post_ms", fallback=mdx_defaults["preview_post_ms"]
        )

        # General
        general_defaults = defaults["General"]
        self.log_level_str = self._config.get("General", "log_level", fallback=general_defaults["log_level"])
        self.log_level = self._get_log_level(self.log_level_str)

        # GPU Pack settings
        self.gpu_opt_in = self._config.getboolean("General", "gpu_opt_in", fallback=general_defaults["gpu_opt_in"])
        self.gpu_flavor = self._config.get("General", "gpu_flavor", fallback=general_defaults["gpu_flavor"])
        self.gpu_pack_installed_version = self._config.get(
            "General", "gpu_pack_installed_version", fallback=general_defaults["gpu_pack_installed_version"]
        )
        self.gpu_pack_path = self._resolve_path_from_config(
            self._config.get("General", "gpu_pack_path", fallback=general_defaults["gpu_pack_path"])
        )
        self.gpu_last_health = self._config.get(
            "General", "gpu_last_health", fallback=general_defaults["gpu_last_health"]
        )
        self.gpu_last_error = self._config.get("General", "gpu_last_error", fallback=general_defaults["gpu_last_error"])
        self.gpu_pack_dialog_dont_show = self._config.getboolean(
            "General", "gpu_pack_dialog_dont_show", fallback=general_defaults["gpu_pack_dialog_dont_show"]
        )
        self.gpu_pack_dont_ask = self._config.getboolean(
            "General", "gpu_pack_dont_ask", fallback=general_defaults["gpu_pack_dont_ask"]
        )
        self.splash_dont_show_health = self._config.getboolean(
            "General", "splash_dont_show_health", fallback=general_defaults["splash_dont_show_health"]
        )
        self.prefer_system_pytorch = self._config.getboolean(
            "General", "prefer_system_pytorch", fallback=general_defaults["prefer_system_pytorch"]
        )
        self.song_list_batch_size = self._config.getint(
            "General", "song_list_batch_size", fallback=general_defaults["song_list_batch_size"]
        )

        # Audio
        audio_defaults = defaults["Audio"]
        self.default_volume = self._config.getfloat(
            "Audio", "default_volume", fallback=audio_defaults["default_volume"]
        )
        self.auto_play = self._config.getboolean("Audio", "auto_play", fallback=audio_defaults["auto_play"])

        # Window geometry
        window_defaults = defaults["Window"]
        self.window_width = self._config.getint("Window", "width", fallback=window_defaults["width"])
        self.window_height = self._config.getint("Window", "height", fallback=window_defaults["height"])
        self.window_x = self._config.getint("Window", "x", fallback=window_defaults["x"])
        self.window_y = self._config.getint("Window", "y", fallback=window_defaults["y"])
        self.window_maximized = self._config.getboolean("Window", "maximized", fallback=window_defaults["maximized"])
        # Splitter position (stored as comma-separated list)
        splitter_pos_str = self._config.get(
            "Window", "main_splitter_pos", fallback=window_defaults["main_splitter_pos"]
        )
        self.main_splitter_pos = [int(x.strip()) for x in splitter_pos_str.split(",")]
        second_splitter_pos_str = self._config.get(
            "Window", "second_splitter_pos", fallback=window_defaults["second_splitter_pos"]
        )
        self.second_splitter_pos = [int(x.strip()) for x in second_splitter_pos_str.split(",")]

        # WatchMode
        watch_mode_defaults = defaults["WatchMode"]
        self.watch_mode_default = self._config.getboolean(
            "WatchMode", "watch_mode_default", fallback=watch_mode_defaults["watch_mode_default"]
        )
        self.watch_debounce_ms = self._config.getint(
            "WatchMode", "watch_debounce_ms", fallback=watch_mode_defaults["watch_debounce_ms"]
        )
        self.watch_ignore_patterns = self._config.get(
            "WatchMode", "watch_ignore_patterns", fallback=watch_mode_defaults["watch_ignore_patterns"]
        )

        logger.debug(f"Configuration loaded: {self.config_path}")

    # Path Helper Properties
    # These provide centralized, consistent path resolution with proper fallbacks

    @property
    def data_dir(self) -> str:
        """
        Get the base application data directory.

        Returns:
            str: Path to %LOCALAPPDATA%/USDXFixGap/ (Windows) or equivalent on other platforms
        """
        return get_localappdata_dir()

    @property
    def gpu_runtime_root(self) -> str:
        """
        Get the GPU Pack runtime root directory.

        Returns:
            str: Path to {data_dir}/gpu_runtime/
        """
        return os.path.join(self.data_dir, "gpu_runtime")

    def get_gpu_pack_dir(self, torch_version: str) -> str:
        """
        Get the GPU Pack installation directory for a specific PyTorch version.

        Args:
            torch_version: PyTorch version (e.g., "2.4.1+cu121" or "2.4.1-cu121")

        Returns:
            str: Path to {data_dir}/gpu_runtime/torch-{version}/

        Example:
            >>> config.get_gpu_pack_dir("2.4.1+cu121")
            'C:/Users/user/AppData/Local/USDXFixGap/gpu_runtime/torch-2.4.1-cu121'
        """
        # Normalize version to use dashes
        normalized = torch_version.replace("+", "-")
        if not normalized.startswith("torch-"):
            normalized = f"torch-{normalized}"
        return os.path.join(self.gpu_runtime_root, normalized)

    @property
    def effective_models_directory(self) -> str:
        """
        Get the effective models directory (respects user config or uses default).

        Returns:
            str: User-configured path or default {data_dir}/models/
        """
        if self.models_directory:
            return self.models_directory
        return os.path.join(self.data_dir, "models")

    @property
    def effective_gpu_pack_path(self) -> str:
        """
        Get the effective GPU Pack path (respects user config or empty string if not set).

        Returns:
            str: User-configured GPU Pack path or empty string
        """
        return self.gpu_pack_path or ""

    def _get_log_level(self, level_str):
        """Convert string log level to logging level constant"""
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return levels.get(level_str.upper(), logging.INFO)  # Default to INFO if invalid

    def _update_paths_section(self, config: configparser.ConfigParser):
        """Update Paths section in config."""
        if not config.has_section("Paths"):
            config.add_section("Paths")
        old_last_dir = config.get("Paths", "last_directory", fallback="")
        new_last_dir = self._make_path_portable(self.last_directory or "")
        if old_last_dir != new_last_dir:
            logger.debug(f"Config.save(): Updating last_directory: '{old_last_dir}' → '{new_last_dir}'")
        config["Paths"]["last_directory"] = new_last_dir

    def _update_general_section(self, config: configparser.ConfigParser):
        """Update General section in config."""
        if not config.has_section("General"):
            config.add_section("General")
        config["General"]["gpu_opt_in"] = "true" if self.gpu_opt_in else "false"
        config["General"]["gpu_flavor"] = self.gpu_flavor
        config["General"]["gpu_pack_installed_version"] = self.gpu_pack_installed_version
        config["General"]["gpu_pack_path"] = self._make_path_portable(self.gpu_pack_path)
        config["General"]["gpu_last_health"] = self.gpu_last_health
        config["General"]["gpu_last_error"] = self.gpu_last_error
        config["General"]["gpu_pack_dialog_dont_show"] = "true" if self.gpu_pack_dialog_dont_show else "false"
        config["General"]["gpu_pack_dont_ask"] = "true" if self.gpu_pack_dont_ask else "false"
        config["General"]["splash_dont_show_health"] = "true" if self.splash_dont_show_health else "false"
        config["General"]["prefer_system_pytorch"] = "true" if self.prefer_system_pytorch else "false"
        config["General"]["song_list_batch_size"] = str(self.song_list_batch_size)

    def _update_window_section(self, config: configparser.ConfigParser):
        """Update Window section in config."""
        if not config.has_section("Window"):
            config.add_section("Window")
        config["Window"]["width"] = str(self.window_width)
        config["Window"]["height"] = str(self.window_height)
        config["Window"]["x"] = str(self.window_x)
        config["Window"]["y"] = str(self.window_y)
        config["Window"]["maximized"] = "true" if self.window_maximized else "false"
        config["Window"]["main_splitter_pos"] = ",".join(str(x) for x in self.main_splitter_pos)
        config["Window"]["second_splitter_pos"] = ",".join(str(x) for x in self.second_splitter_pos)

    def _create_backup(self):
        """Create backup of config file before modifying."""
        import shutil

        if os.path.exists(self.config_path):
            backup_path = self.config_path + ".bak"
            try:
                shutil.copy2(self.config_path, backup_path)
                logger.debug(f"Created backup at {backup_path}")
            except Exception as e:
                logger.warning(f"Failed to create backup: {e}")

    def save(self):
        """Save current configuration to file with minimal mutation.

        Re-reads the existing config file, updates ONLY managed keys,
        creates a backup, and preserves all unrelated sections/keys.
        """
        logger.debug(f"Config.save() called: last_directory property = '{self.last_directory}'")

        # Create a fresh ConfigParser to read the current file state
        current = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            try:
                current.read(self.config_path, encoding="utf-8-sig")
                logger.debug(f"Re-read existing config from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to re-read config file: {e}. Will create fresh config.")

        # Create backup before modifying
        self._create_backup()

        # Update managed sections
        self._update_paths_section(current)
        self._update_general_section(current)
        self._update_window_section(current)

        # Write back to file
        try:
            with open(self.config_path, "w", encoding="utf-8") as configfile:
                current.write(configfile)
            logger.debug(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise

    def save_config(self):
        """Alias for save() to match bootstrap expectations"""
        self.save()

    def log_config_location(self):
        """Log the configuration file location (call after logging is set up)"""
        print(f"Configuration loaded from: {self.config_path}")
        logger.info(f"Configuration loaded from: {self.config_path}")
