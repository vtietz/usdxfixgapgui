import os
import configparser
import logging
from PySide6.QtCore import QObject
from utils.files import get_localappdata_dir

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
            if 'PYTEST_CURRENT_TEST' in os.environ:
                import tempfile
                test_config_dir = os.path.join(tempfile.gettempdir(), 'usdxfixgap_test')
                os.makedirs(test_config_dir, exist_ok=True)
                self.config_path = os.path.join(test_config_dir, 'config.ini')
                logger.debug(f"Test mode detected, using temp config: {self.config_path}")
            else:
                self.config_path = os.path.join(get_localappdata_dir(), 'config.ini')
        
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
            with open(self.config_path, 'w') as configfile:
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

    def _set_defaults(self):
        """Set default configuration values"""
        self._config['Paths'] = {
            'tmp_root': os.path.join(get_localappdata_dir(), '.tmp'),
            'default_directory': os.path.join(get_localappdata_dir(), 'samples'),
            'last_directory': '',  # New parameter for last used directory
            'models_directory': ''  # Empty = use default (LOCALAPPDATA/models), can be customized
        }

        self._config['Detection'] = {
            'default_detection_time': '30',
            'gap_tolerance': '500',
            'vocal_start_window_sec': '20',
            'vocal_window_increment_sec': '10',
            'vocal_window_max_sec': '60'
        }

        self._config['Colors'] = {
            'detected_gap_color': 'blue',
            'playback_position_color': 'red',
            'waveform_color': 'gray',
            'silence_periods_color': '105,105,105,128'
        }

        self._config['Player'] = {
            'adjust_player_position_step_audio': '100',
            'adjust_player_position_step_vocals': '10'
        }

        self._config['Processing'] = {
            'method': 'mdx',  # Only MDX is supported
            'normalization_level': '-20',  # Default normalization level is -20 dB
            'auto_normalize': 'false'      # Default is not to auto-normalize
        }

        # MDX settings (Demucs-based with expanding search and GPU optimizations)
        self._config['mdx'] = {
            # Chunked processing
            'chunk_duration_ms': '12000',      # 12s chunks for Demucs processing
            'chunk_overlap_ms': '6000',        # 50% overlap (6s) between chunks

            # Energy analysis (tuned for balanced detection)
            'frame_duration_ms': '25',         # 25ms frames for RMS computation
            'hop_duration_ms': '20',           # 20ms hop for good temporal resolution
            'noise_floor_duration_ms': '1200', # 1.2s for noise floor estimation (more robust)

            # Onset detection thresholds (balanced - gap-focused search enables sensitivity)
            'onset_snr_threshold': '4.5',      # RMS > noise + 4.5*sigma (balanced sensitivity)
            'onset_abs_threshold': '0.012',    # Absolute RMS threshold (1.2% amplitude minimum)
            'min_voiced_duration_ms': '150',   # 150ms minimum sustained vocals
            'hysteresis_ms': '350',            # 350ms hysteresis for onset refinement

            # Expanding search parameters (NEW - balances speed and robustness)
            'initial_radius_ms': '7500',       # Start with ±7.5s window around expected gap
            'radius_increment_ms': '7500',     # Expand by 7.5s each iteration
            'max_expansions': '3',             # Max 3 expansions = ±30s total coverage

            # Performance optimizations (NEW - GPU and CPU speedup)
            'use_fp16': 'false',               # FP16 disabled (type mismatch issues with Demucs)
            'resample_hz': '0',                # 0=disabled, 32000=downsample for CPU speed
            'early_stop_tolerance_ms': '500',  # Early-stop scanning when onset is within tolerance
            'tf32': 'true',                    # Enable TF32 on CUDA for faster matmul

            # Confidence and preview
            'confidence_threshold': '0.55',    # SNR-based confidence threshold
            'preview_pre_ms': '3000',          # Preview window before onset (3s)
            'preview_post_ms': '9000'          # Preview window after onset (9s)
        }

        self._config['General'] = {
            'log_level': 'INFO',
            # GPU Pack settings
            'gpu_opt_in': 'false',
            'gpu_flavor': 'cu121',
            'gpu_pack_installed_version': '',
            'gpu_pack_path': '',
            'gpu_last_health': '',
            'gpu_last_error': '',
            'gpu_pack_dialog_dont_show': 'false',
            'prefer_system_pytorch': 'true'  # Try system PyTorch+CUDA before GPU Pack download
        }

        self._config['Audio'] = {
            'default_volume': '0.5',
            'auto_play': 'False'
        }

        self._config['Window'] = {
            'width': '1024',
            'height': '768',
            'x': '-1',  # -1 means centered
            'y': '-1',   # -1 means centered
            'maximized': 'false'  # Window maximized state
        }

    def _get_defaults(self):
        """Get default configuration values as a dictionary structure."""
        localappdata = get_localappdata_dir()
        return {
            'Paths': {
                'tmp_root': os.path.join(localappdata, '.tmp'),
                'default_directory': os.path.join(localappdata, 'samples'),
                'last_directory': '',
                'models_directory': ''
            },
            'Detection': {
                'default_detection_time': 30,
                'gap_tolerance': 500,
                'vocal_start_window_sec': 20,
                'vocal_window_increment_sec': 10,
                'vocal_window_max_sec': 60
            },
            'Colors': {
                'detected_gap_color': 'blue',
                'playback_position_color': 'red',
                'waveform_color': 'gray',
                'silence_periods_color': '105,105,105,128'
            },
            'Player': {
                'adjust_player_position_step_audio': 100,
                'adjust_player_position_step_vocals': 10
            },
            'Processing': {
                'method': 'mdx',
                'normalization_level': -20,
                'auto_normalize': False
            },
            'mdx': {
                'chunk_duration_ms': 12000,
                'chunk_overlap_ms': 6000,
                'frame_duration_ms': 25,
                'hop_duration_ms': 20,
                'noise_floor_duration_ms': 1200,
                'onset_snr_threshold': 4.5,
                'onset_abs_threshold': 0.012,
                'min_voiced_duration_ms': 150,
                'hysteresis_ms': 350,
                'initial_radius_ms': 7500,
                'radius_increment_ms': 7500,
                'max_expansions': 3,
                'use_fp16': False,
                'resample_hz': 0,
                'early_stop_tolerance_ms': 500,
                'tf32': True,
                'confidence_threshold': 0.55,
                'preview_pre_ms': 3000,
                'preview_post_ms': 9000
            },
            'General': {
                'log_level': 'INFO',
                'gpu_opt_in': False,
                'gpu_flavor': 'cu121',
                'gpu_pack_installed_version': '',
                'gpu_pack_path': '',
                'gpu_last_health': '',
                'gpu_last_error': '',
                'gpu_pack_dialog_dont_show': False,
                'prefer_system_pytorch': True
            },
            'Audio': {
                'default_volume': 0.5,
                'auto_play': False
            },
            'Window': {
                'width': 1024,
                'height': 768,
                'x': -1,
                'y': -1,
                'maximized': False
            }
        }

    def _set_defaults(self):
        """Set default configuration values in the ConfigParser object."""
        defaults = self._get_defaults()
        
        for section, values in defaults.items():
            self._config[section] = {}
            for key, value in values.items():
                # Convert all values to strings for ConfigParser
                if isinstance(value, bool):
                    self._config[section][key] = 'true' if value else 'false'
                else:
                    self._config[section][key] = str(value)

    def _initialize_properties(self):
        """Initialize class properties from config values with fallbacks."""
        defaults = self._get_defaults()
        
        # Paths
        self.tmp_root = self._config.get('Paths', 'tmp_root', fallback=defaults['Paths']['tmp_root'])
        self.default_directory = self._config.get('Paths', 'default_directory', fallback=defaults['Paths']['default_directory'])
        self.last_directory = self._config.get('Paths', 'last_directory', fallback=defaults['Paths']['last_directory'])
        self.models_directory = self._config.get('Paths', 'models_directory', fallback=defaults['Paths']['models_directory'])

        # Detection
        self.default_detection_time = self._config.getint('Detection', 'default_detection_time', fallback=defaults['Detection']['default_detection_time'])
        self.gap_tolerance = self._config.getint('Detection', 'gap_tolerance', fallback=defaults['Detection']['gap_tolerance'])
        self.vocal_start_window_sec = self._config.getint('Detection', 'vocal_start_window_sec', fallback=defaults['Detection']['vocal_start_window_sec'])
        self.vocal_window_increment_sec = self._config.getint('Detection', 'vocal_window_increment_sec', fallback=defaults['Detection']['vocal_window_increment_sec'])
        self.vocal_window_max_sec = self._config.getint('Detection', 'vocal_window_max_sec', fallback=defaults['Detection']['vocal_window_max_sec'])

        # Colors
        self.detected_gap_color = self._config.get('Colors', 'detected_gap_color', fallback=defaults['Colors']['detected_gap_color'])
        self.playback_position_color = self._config.get('Colors', 'playback_position_color', fallback=defaults['Colors']['playback_position_color'])
        self.waveform_color = self._config.get('Colors', 'waveform_color', fallback=defaults['Colors']['waveform_color'])

        # Parse the RGBA tuple
        rgba_str = self._config.get('Colors', 'silence_periods_color', fallback=defaults['Colors']['silence_periods_color'])
        rgba_values = [int(x.strip()) for x in rgba_str.split(',')]
        self.silence_periods_color = tuple(rgba_values)

        # Player
        self.adjust_player_position_step_audio = self._config.getint('Player', 'adjust_player_position_step_audio', fallback=defaults['Player']['adjust_player_position_step_audio'])
        self.adjust_player_position_step_vocals = self._config.getint('Player', 'adjust_player_position_step_vocals', fallback=defaults['Player']['adjust_player_position_step_vocals'])

        # Processing
        self.method = self._config.get('Processing', 'method', fallback=defaults['Processing']['method'])
        self.normalization_level = self._config.getint('Processing', 'normalization_level', fallback=defaults['Processing']['normalization_level'])
        self.auto_normalize = self._config.getboolean('Processing', 'auto_normalize', fallback=defaults['Processing']['auto_normalize'])

        # MDX settings (all with fallbacks)
        mdx_defaults = defaults['mdx']
        self.mdx_chunk_duration_ms = self._config.getint('mdx', 'chunk_duration_ms', fallback=mdx_defaults['chunk_duration_ms'])
        self.mdx_chunk_overlap_ms = self._config.getint('mdx', 'chunk_overlap_ms', fallback=mdx_defaults['chunk_overlap_ms'])
        self.mdx_frame_duration_ms = self._config.getint('mdx', 'frame_duration_ms', fallback=mdx_defaults['frame_duration_ms'])
        self.mdx_hop_duration_ms = self._config.getint('mdx', 'hop_duration_ms', fallback=mdx_defaults['hop_duration_ms'])
        self.mdx_noise_floor_duration_ms = self._config.getint('mdx', 'noise_floor_duration_ms', fallback=mdx_defaults['noise_floor_duration_ms'])
        self.mdx_onset_snr_threshold = self._config.getfloat('mdx', 'onset_snr_threshold', fallback=mdx_defaults['onset_snr_threshold'])
        self.mdx_onset_abs_threshold = self._config.getfloat('mdx', 'onset_abs_threshold', fallback=mdx_defaults['onset_abs_threshold'])
        self.mdx_min_voiced_duration_ms = self._config.getint('mdx', 'min_voiced_duration_ms', fallback=mdx_defaults['min_voiced_duration_ms'])
        self.mdx_hysteresis_ms = self._config.getint('mdx', 'hysteresis_ms', fallback=mdx_defaults['hysteresis_ms'])
        # Expanding search parameters
        self.mdx_initial_radius_ms = self._config.getint('mdx', 'initial_radius_ms', fallback=mdx_defaults['initial_radius_ms'])
        self.mdx_radius_increment_ms = self._config.getint('mdx', 'radius_increment_ms', fallback=mdx_defaults['radius_increment_ms'])
        self.mdx_max_expansions = self._config.getint('mdx', 'max_expansions', fallback=mdx_defaults['max_expansions'])
        # Performance optimizations
        self.mdx_use_fp16 = self._config.getboolean('mdx', 'use_fp16', fallback=mdx_defaults['use_fp16'])
        self.mdx_resample_hz = self._config.getint('mdx', 'resample_hz', fallback=mdx_defaults['resample_hz'])
        self.mdx_early_stop_tolerance_ms = self._config.getint('mdx', 'early_stop_tolerance_ms', fallback=mdx_defaults['early_stop_tolerance_ms'])
        self.mdx_tf32 = self._config.getboolean('mdx', 'tf32', fallback=mdx_defaults['tf32'])
        # Confidence and preview
        self.mdx_confidence_threshold = self._config.getfloat('mdx', 'confidence_threshold', fallback=mdx_defaults['confidence_threshold'])
        self.mdx_preview_pre_ms = self._config.getint('mdx', 'preview_pre_ms', fallback=mdx_defaults['preview_pre_ms'])
        self.mdx_preview_post_ms = self._config.getint('mdx', 'preview_post_ms', fallback=mdx_defaults['preview_post_ms'])

        # General
        general_defaults = defaults['General']
        self.log_level_str = self._config.get('General', 'log_level', fallback=general_defaults['log_level'])
        self.log_level = self._get_log_level(self.log_level_str)

        # GPU Pack settings
        self.gpu_opt_in = self._config.getboolean('General', 'gpu_opt_in', fallback=general_defaults['gpu_opt_in'])
        self.gpu_flavor = self._config.get('General', 'gpu_flavor', fallback=general_defaults['gpu_flavor'])
        self.gpu_pack_installed_version = self._config.get('General', 'gpu_pack_installed_version', fallback=general_defaults['gpu_pack_installed_version'])
        self.gpu_pack_path = self._config.get('General', 'gpu_pack_path', fallback=general_defaults['gpu_pack_path'])
        self.gpu_last_health = self._config.get('General', 'gpu_last_health', fallback=general_defaults['gpu_last_health'])
        self.gpu_last_error = self._config.get('General', 'gpu_last_error', fallback=general_defaults['gpu_last_error'])
        self.gpu_pack_dialog_dont_show = self._config.getboolean('General', 'gpu_pack_dialog_dont_show', fallback=general_defaults['gpu_pack_dialog_dont_show'])
        self.prefer_system_pytorch = self._config.getboolean('General', 'prefer_system_pytorch', fallback=general_defaults['prefer_system_pytorch'])

        # Audio
        audio_defaults = defaults['Audio']
        self.default_volume = self._config.getfloat('Audio', 'default_volume', fallback=audio_defaults['default_volume'])
        self.auto_play = self._config.getboolean('Audio', 'auto_play', fallback=audio_defaults['auto_play'])

        # Window geometry
        window_defaults = defaults['Window']
        self.window_width = self._config.getint('Window', 'width', fallback=window_defaults['width'])
        self.window_height = self._config.getint('Window', 'height', fallback=window_defaults['height'])
        self.window_x = self._config.getint('Window', 'x', fallback=window_defaults['x'])
        self.window_y = self._config.getint('Window', 'y', fallback=window_defaults['y'])
        self.window_maximized = self._config.getboolean('Window', 'maximized', fallback=window_defaults['maximized'])

        logger.debug(f"Configuration loaded: {self.config_path}")

    def _get_log_level(self, level_str):
        """Convert string log level to logging level constant"""
        levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return levels.get(level_str.upper(), logging.INFO)  # Default to INFO if invalid

    def save(self):
        """Save current configuration to file with minimal mutation.
        
        Re-reads the existing config file, updates ONLY managed keys,
        creates a backup, and preserves all unrelated sections/keys.
        """
        import shutil
        
        logger.debug(f"Config.save() called: last_directory property = '{self.last_directory}'")
        
        # Create a fresh ConfigParser to read the current file state
        current = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            try:
                current.read(self.config_path, encoding='utf-8-sig')
                logger.debug(f"Re-read existing config from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to re-read config file: {e}. Will create fresh config.")
        
        # Create backup before modifying
        if os.path.exists(self.config_path):
            backup_path = self.config_path + '.bak'
            try:
                shutil.copy2(self.config_path, backup_path)
                logger.debug(f"Created backup at {backup_path}")
            except Exception as e:
                logger.warning(f"Failed to create backup: {e}")
        
        # Update ONLY managed keys (minimal mutation)
        # 1. Paths section - last_directory
        if not current.has_section('Paths'):
            current.add_section('Paths')
        old_last_dir = current.get('Paths', 'last_directory', fallback='')
        new_last_dir = self.last_directory or ''
        if old_last_dir != new_last_dir:
            logger.debug(f"Config.save(): Updating last_directory: '{old_last_dir}' → '{new_last_dir}'")
        current['Paths']['last_directory'] = new_last_dir
        
        # 2. General section - GPU Pack settings
        if not current.has_section('General'):
            current.add_section('General')
        current['General']['gpu_opt_in'] = 'true' if self.gpu_opt_in else 'false'
        current['General']['gpu_flavor'] = self.gpu_flavor
        current['General']['gpu_pack_installed_version'] = self.gpu_pack_installed_version
        current['General']['gpu_pack_path'] = self.gpu_pack_path
        current['General']['gpu_last_health'] = self.gpu_last_health
        current['General']['gpu_last_error'] = self.gpu_last_error
        current['General']['gpu_pack_dialog_dont_show'] = 'true' if self.gpu_pack_dialog_dont_show else 'false'
        current['General']['prefer_system_pytorch'] = 'true' if self.prefer_system_pytorch else 'false'
        
        # 3. Window section - geometry
        if not current.has_section('Window'):
            current.add_section('Window')
        current['Window']['width'] = str(self.window_width)
        current['Window']['height'] = str(self.window_height)
        current['Window']['x'] = str(self.window_x)
        current['Window']['y'] = str(self.window_y)
        current['Window']['maximized'] = 'true' if self.window_maximized else 'false'
        
        # Write back to file
        try:
            with open(self.config_path, 'w', encoding='utf-8') as configfile:
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
