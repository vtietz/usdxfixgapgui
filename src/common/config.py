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

    def _get_defaults(self):
        """Get default configuration values as a dictionary structure."""
        # Lazy import: Defer MdxConfig import to avoid importing torch at Config instantiation.
        # CRITICAL: This import must happen after GPU bootstrap to ensure torch comes from GPU Pack.
        # The mdx package __init__.py now uses lazy imports via __getattr__ to avoid
        # importing torch-dependent modules (separator.py, model_loader.py) at package load time.
        from utils.providers.mdx.config import MdxConfig

        # Create default instance to extract values
        mdx_defaults = MdxConfig()

        localappdata = get_localappdata_dir()

        # In portable mode, use relative paths for app-internal directories
        if is_portable_mode():
            tmp_root = "./.tmp"
            default_directory = "./samples"
            models_directory = ""
        else:
            tmp_root = os.path.join(localappdata, ".tmp")
            default_directory = os.path.join(localappdata, "samples")
            models_directory = ""

        return {
            "Paths": {
                "tmp_root": tmp_root,
                "default_directory": default_directory,
                "last_directory": "",
                "models_directory": models_directory,
            },
            "Detection": {
                "default_detection_time": 30,
                "gap_tolerance": 500,
                "vocal_start_window_sec": int(mdx_defaults.start_window_ms / 1000),
                "vocal_window_increment_sec": int(mdx_defaults.start_window_increment_ms / 1000),
                "vocal_window_max_sec": int(mdx_defaults.start_window_max_ms / 1000),
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
                "chunk_duration_ms": mdx_defaults.chunk_duration_ms,
                "chunk_overlap_ms": mdx_defaults.chunk_overlap_ms,
                "frame_duration_ms": mdx_defaults.frame_duration_ms,
                "hop_duration_ms": mdx_defaults.hop_duration_ms,
                "noise_floor_duration_ms": mdx_defaults.noise_floor_duration_ms,
                "onset_snr_threshold": mdx_defaults.onset_snr_threshold,
                "onset_abs_threshold": mdx_defaults.onset_abs_threshold,
                "min_voiced_duration_ms": mdx_defaults.min_voiced_duration_ms,
                "hysteresis_ms": mdx_defaults.hysteresis_ms,
                "initial_radius_ms": mdx_defaults.initial_radius_ms,
                "radius_increment_ms": mdx_defaults.radius_increment_ms,
                "max_expansions": mdx_defaults.max_expansions,
                "use_fp16": mdx_defaults.use_fp16,
                "resample_hz": mdx_defaults.resample_hz,
                "early_stop_tolerance_ms": mdx_defaults.early_stop_tolerance_ms,
                "tf32": mdx_defaults.tf32,
                "confidence_threshold": mdx_defaults.confidence_threshold,
                "preview_pre_ms": mdx_defaults.preview_pre_ms,
                "preview_post_ms": mdx_defaults.preview_post_ms,
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
                "filter_text": "",
                "filter_statuses": "",
            },
            "WatchMode": {
                "watch_mode_default": False,
                "watch_debounce_ms": 500,
                "watch_ignore_patterns": ".tmp,~,.crdownload,.part,tmp,_processed.",
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

        self._init_paths(defaults)
        self._init_detection(defaults)
        self._init_colors(defaults)
        self._init_player(defaults)
        self._init_processing(defaults)
        self._init_mdx(defaults)
        self._init_general(defaults)
        self._init_audio(defaults)
        self._init_window(defaults)
        self._init_watch_mode(defaults)

        logger.debug("Configuration loaded: %s", self.config_path)

    def _init_paths(self, defaults: dict):
        """Initialize Paths section properties."""
        self.tmp_root = self._resolve_path_from_config(
            self._config.get("Paths", "tmp_root", fallback=defaults["Paths"]["tmp_root"])
        )
        self.default_directory = self._resolve_path_from_config(
            self._config.get("Paths", "default_directory", fallback=defaults["Paths"]["default_directory"])
        )
        self.last_directory = self._resolve_path_from_config(
            self._config.get("Paths", "last_directory", fallback=defaults["Paths"]["last_directory"])
        )
        self.models_directory = self._resolve_path_from_config(
            self._config.get("Paths", "models_directory", fallback=defaults["Paths"]["models_directory"])
        )

    def _init_detection(self, defaults: dict):
        """Initialize Detection section properties."""
        d = defaults["Detection"]
        self.default_detection_time = self._config.getint(
            "Detection", "default_detection_time", fallback=d["default_detection_time"]
        )
        self.gap_tolerance = self._config.getint("Detection", "gap_tolerance", fallback=d["gap_tolerance"])
        self.vocal_start_window_sec = self._config.getint(
            "Detection", "vocal_start_window_sec", fallback=d["vocal_start_window_sec"]
        )
        self.vocal_window_increment_sec = self._config.getint(
            "Detection", "vocal_window_increment_sec", fallback=d["vocal_window_increment_sec"]
        )
        self.vocal_window_max_sec = self._config.getint(
            "Detection", "vocal_window_max_sec", fallback=d["vocal_window_max_sec"]
        )

    def _init_colors(self, defaults: dict):
        """Initialize Colors section properties."""
        c = defaults["Colors"]
        self.detected_gap_color = self._config.get("Colors", "detected_gap_color", fallback=c["detected_gap_color"])
        self.playback_position_color = self._config.get(
            "Colors", "playback_position_color", fallback=c["playback_position_color"]
        )
        self.waveform_color = self._config.get("Colors", "waveform_color", fallback=c["waveform_color"])

        # Parse the RGBA tuple
        rgba_str = self._config.get("Colors", "silence_periods_color", fallback=c["silence_periods_color"])
        rgba_values = [int(x.strip()) for x in rgba_str.split(",")]
        self.silence_periods_color = tuple(rgba_values)

    def _init_player(self, defaults: dict):
        """Initialize Player section properties."""
        p = defaults["Player"]
        self.adjust_player_position_step_audio = self._config.getint(
            "Player", "adjust_player_position_step_audio", fallback=p["adjust_player_position_step_audio"]
        )
        self.adjust_player_position_step_vocals = self._config.getint(
            "Player", "adjust_player_position_step_vocals", fallback=p["adjust_player_position_step_vocals"]
        )

    def _init_processing(self, defaults: dict):
        """Initialize Processing section properties."""
        p = defaults["Processing"]
        self.method = self._config.get("Processing", "method", fallback=p["method"])
        self.normalization_level = self._config.getint(
            "Processing", "normalization_level", fallback=p["normalization_level"]
        )
        self.auto_normalize = self._config.getboolean("Processing", "auto_normalize", fallback=p["auto_normalize"])

    def _init_mdx(self, defaults: dict):
        """Initialize MDX section properties."""
        m = defaults["mdx"]
        # Chunking parameters
        self.mdx_chunk_duration_ms = self._config.getint("mdx", "chunk_duration_ms", fallback=m["chunk_duration_ms"])
        self.mdx_chunk_overlap_ms = self._config.getint("mdx", "chunk_overlap_ms", fallback=m["chunk_overlap_ms"])
        self.mdx_frame_duration_ms = self._config.getint("mdx", "frame_duration_ms", fallback=m["frame_duration_ms"])
        self.mdx_hop_duration_ms = self._config.getint("mdx", "hop_duration_ms", fallback=m["hop_duration_ms"])
        self.mdx_noise_floor_duration_ms = self._config.getint(
            "mdx", "noise_floor_duration_ms", fallback=m["noise_floor_duration_ms"]
        )
        # Onset detection thresholds
        self.mdx_onset_snr_threshold = self._config.getfloat(
            "mdx", "onset_snr_threshold", fallback=m["onset_snr_threshold"]
        )
        self.mdx_onset_abs_threshold = self._config.getfloat(
            "mdx", "onset_abs_threshold", fallback=m["onset_abs_threshold"]
        )
        self.mdx_min_voiced_duration_ms = self._config.getint(
            "mdx", "min_voiced_duration_ms", fallback=m["min_voiced_duration_ms"]
        )
        self.mdx_hysteresis_ms = self._config.getint("mdx", "hysteresis_ms", fallback=m["hysteresis_ms"])
        # Expanding search parameters
        self.mdx_initial_radius_ms = self._config.getint("mdx", "initial_radius_ms", fallback=m["initial_radius_ms"])
        self.mdx_radius_increment_ms = self._config.getint(
            "mdx", "radius_increment_ms", fallback=m["radius_increment_ms"]
        )
        self.mdx_max_expansions = self._config.getint("mdx", "max_expansions", fallback=m["max_expansions"])
        # Performance optimizations
        self.mdx_use_fp16 = self._config.getboolean("mdx", "use_fp16", fallback=m["use_fp16"])
        self.mdx_resample_hz = self._config.getint("mdx", "resample_hz", fallback=m["resample_hz"])
        self.mdx_early_stop_tolerance_ms = self._config.getint(
            "mdx", "early_stop_tolerance_ms", fallback=m["early_stop_tolerance_ms"]
        )
        self.mdx_tf32 = self._config.getboolean("mdx", "tf32", fallback=m["tf32"])
        # Confidence and preview
        self.mdx_confidence_threshold = self._config.getfloat(
            "mdx", "confidence_threshold", fallback=m["confidence_threshold"]
        )
        self.mdx_preview_pre_ms = self._config.getint("mdx", "preview_pre_ms", fallback=m["preview_pre_ms"])
        self.mdx_preview_post_ms = self._config.getint("mdx", "preview_post_ms", fallback=m["preview_post_ms"])

    def _init_general(self, defaults: dict):
        """Initialize General section properties."""
        g = defaults["General"]
        # Logging
        self.log_level_str = self._config.get("General", "log_level", fallback=g["log_level"])
        self.log_level = self._get_log_level(self.log_level_str)
        # GPU Pack settings
        self.gpu_opt_in = self._config.getboolean("General", "gpu_opt_in", fallback=g["gpu_opt_in"])
        self.gpu_flavor = self._config.get("General", "gpu_flavor", fallback=g["gpu_flavor"])
        self.gpu_pack_installed_version = self._config.get(
            "General", "gpu_pack_installed_version", fallback=g["gpu_pack_installed_version"]
        )
        self.gpu_pack_path = self._resolve_path_from_config(
            self._config.get("General", "gpu_pack_path", fallback=g["gpu_pack_path"])
        )
        self.gpu_last_health = self._config.get("General", "gpu_last_health", fallback=g["gpu_last_health"])
        self.gpu_last_error = self._config.get("General", "gpu_last_error", fallback=g["gpu_last_error"])
        self.gpu_pack_dialog_dont_show = self._config.getboolean(
            "General", "gpu_pack_dialog_dont_show", fallback=g["gpu_pack_dialog_dont_show"]
        )
        self.gpu_pack_dont_ask = self._config.getboolean(
            "General", "gpu_pack_dont_ask", fallback=g["gpu_pack_dont_ask"]
        )
        self.splash_dont_show_health = self._config.getboolean(
            "General", "splash_dont_show_health", fallback=g["splash_dont_show_health"]
        )
        self.prefer_system_pytorch = self._config.getboolean(
            "General", "prefer_system_pytorch", fallback=g["prefer_system_pytorch"]
        )
        self.song_list_batch_size = self._config.getint(
            "General", "song_list_batch_size", fallback=g["song_list_batch_size"]
        )

    def _init_audio(self, defaults: dict):
        """Initialize Audio section properties."""
        a = defaults["Audio"]
        self.default_volume = self._config.getfloat("Audio", "default_volume", fallback=a["default_volume"])
        self.auto_play = self._config.getboolean("Audio", "auto_play", fallback=a["auto_play"])

    def _init_window(self, defaults: dict):
        """Initialize Window section properties."""
        w = defaults["Window"]
        self.window_width = self._config.getint("Window", "width", fallback=w["width"])
        self.window_height = self._config.getint("Window", "height", fallback=w["height"])
        self.window_x = self._config.getint("Window", "x", fallback=w["x"])
        self.window_y = self._config.getint("Window", "y", fallback=w["y"])
        self.window_maximized = self._config.getboolean("Window", "maximized", fallback=w["maximized"])
        # Splitter positions (stored as comma-separated lists)
        splitter_pos_str = self._config.get("Window", "main_splitter_pos", fallback=w["main_splitter_pos"])
        self.main_splitter_pos = [int(x.strip()) for x in splitter_pos_str.split(",")]
        second_splitter_pos_str = self._config.get("Window", "second_splitter_pos", fallback=w["second_splitter_pos"])
        self.second_splitter_pos = [int(x.strip()) for x in second_splitter_pos_str.split(",")]
        # Filter state
        self.filter_text = self._config.get("Window", "filter_text", fallback=w["filter_text"])
        filter_statuses_str = self._config.get("Window", "filter_statuses", fallback=w["filter_statuses"])
        self.filter_statuses = [s.strip() for s in filter_statuses_str.split(",") if s.strip()]

    def _init_watch_mode(self, defaults: dict):
        """Initialize WatchMode section properties."""
        wm = defaults["WatchMode"]
        self.watch_mode_default = self._config.getboolean(
            "WatchMode", "watch_mode_default", fallback=wm["watch_mode_default"]
        )
        self.watch_debounce_ms = self._config.getint("WatchMode", "watch_debounce_ms", fallback=wm["watch_debounce_ms"])
        self.watch_ignore_patterns = self._config.get(
            "WatchMode", "watch_ignore_patterns", fallback=wm["watch_ignore_patterns"]
        )

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

    def get(self, section: str, key: str, fallback: str | None = None) -> str:
        """Get a string value from the config."""
        return self._config.get(section, key, fallback=fallback)

    def get_int(self, section: str, key: str, fallback: int | None = None) -> int:
        """Get an integer value from the config."""
        return self._config.getint(section, key, fallback=fallback)

    def get_float(self, section: str, key: str, fallback: float | None = None) -> float:
        """Get a float value from the config."""
        return self._config.getfloat(section, key, fallback=fallback)

    def get_bool(self, section: str, key: str, fallback: bool | None = None) -> bool:
        """Get a boolean value from the config."""
        return self._config.getboolean(section, key, fallback=fallback)

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

        # Convert paths to relative in portable mode
        config["Paths"]["tmp_root"] = self._make_path_portable(self.tmp_root or "")
        config["Paths"]["default_directory"] = self._make_path_portable(self.default_directory or "")
        config["Paths"]["models_directory"] = self._make_path_portable(self.models_directory or "")

        # last_directory can be absolute (user's external song folders)
        old_last_dir = config.get("Paths", "last_directory", fallback="")
        new_last_dir = self.last_directory or ""
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
        config["Window"]["filter_text"] = self.filter_text
        config["Window"]["filter_statuses"] = ",".join(self.filter_statuses)

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
        config_loaded = False

        if os.path.exists(self.config_path):
            try:
                current.read(self.config_path, encoding="utf-8-sig")
                logger.debug(f"Re-read existing config from {self.config_path}")
                config_loaded = True
            except Exception as e:
                logger.warning(f"Failed to re-read config file: {e}. Will create fresh config.")

        # If config doesn't exist or failed to load, populate with defaults
        if not config_loaded:
            logger.debug("Populating config with defaults before save")
            defaults = self._get_defaults()
            for section, values in defaults.items():
                current[section] = {}
                for key, value in values.items():
                    # Convert all values to strings for ConfigParser
                    if isinstance(value, bool):
                        current[section][key] = "true" if value else "false"
                    else:
                        current[section][key] = str(value)

        # Create backup before modifying
        self._create_backup()

        # Update managed sections (these override defaults/existing values)
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
