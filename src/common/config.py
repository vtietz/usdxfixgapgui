import os
import configparser
import logging
from PySide6.QtCore import QObject
from utils.files import get_localappdata_dir

logger = logging.getLogger(__name__)

class Config(QObject):
    def __init__(self):
        super().__init__()
        self._config = configparser.ConfigParser()

        # Set default values first
        self._set_defaults()

        # Ensure config file exists (creates with defaults if it doesn't)
        self.config_path = self.ensure_config_file_exists()

        # Load the config file (either existing or newly created)
        self._config.read(self.config_path)

        # Initialize properties from config values
        self._initialize_properties()

    def ensure_config_file_exists(self):
        """Create default config file if it doesn't exist."""
        config_path = os.path.join(get_localappdata_dir(), 'config.ini')

        if not os.path.exists(config_path):
            logger.info(f"Config file not found. Creating default config at: {config_path}")

            # Write the config file with default values
            with open(config_path, 'w') as configfile:
                self._config.write(configfile)

            logger.info("Default config.ini created successfully")
        else:
            logger.debug(f"Config file already exists at: {config_path}")

        return config_path

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

            # Onset detection thresholds (optimized for gradual fade-ins)
            'onset_snr_threshold': '6.5',      # RMS > noise + 6.5*sigma (catches gradual onsets)
            'onset_abs_threshold': '0.020',    # Absolute RMS threshold (2.0% amplitude minimum)
            'min_voiced_duration_ms': '200',   # 200ms minimum sustained vocals (shorter for quick starts)
            'hysteresis_ms': '300',            # 300ms hysteresis for better early onset detection

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

    def _initialize_properties(self):
        """Initialize class properties from config values"""
        # Paths
        self.tmp_root = self._config.get('Paths', 'tmp_root')
        self.default_directory = self._config.get('Paths', 'default_directory')
        self.last_directory = self._config.get('Paths', 'last_directory')
        self.models_directory = self._config.get('Paths', 'models_directory')  # NEW: Custom models path

        # Detection
        self.default_detection_time = self._config.getint('Detection', 'default_detection_time')
        self.gap_tolerance = self._config.getint('Detection', 'gap_tolerance')
        self.vocal_start_window_sec = self._config.getint('Detection', 'vocal_start_window_sec')
        self.vocal_window_increment_sec = self._config.getint('Detection', 'vocal_window_increment_sec')
        self.vocal_window_max_sec = self._config.getint('Detection', 'vocal_window_max_sec')

        # Colors
        self.detected_gap_color = self._config.get('Colors', 'detected_gap_color')
        self.playback_position_color = self._config.get('Colors', 'playback_position_color')
        self.waveform_color = self._config.get('Colors', 'waveform_color')

        # Parse the RGBA tuple
        rgba_str = self._config.get('Colors', 'silence_periods_color')
        rgba_values = [int(x.strip()) for x in rgba_str.split(',')]
        self.silence_periods_color = tuple(rgba_values)

        # Player
        self.adjust_player_position_step_audio = self._config.getint('Player', 'adjust_player_position_step_audio')
        self.adjust_player_position_step_vocals = self._config.getint('Player', 'adjust_player_position_step_vocals')

        # Processing
        self.method = self._config.get('Processing', 'method')
        self.normalization_level = self._config.getint('Processing', 'normalization_level')
        self.auto_normalize = self._config.getboolean('Processing', 'auto_normalize')

        # MDX settings
        if self._config.has_section('mdx'):
            self.mdx_chunk_duration_ms = self._config.getint('mdx', 'chunk_duration_ms')
            self.mdx_chunk_overlap_ms = self._config.getint('mdx', 'chunk_overlap_ms')
            self.mdx_frame_duration_ms = self._config.getint('mdx', 'frame_duration_ms')
            self.mdx_hop_duration_ms = self._config.getint('mdx', 'hop_duration_ms')
            self.mdx_noise_floor_duration_ms = self._config.getint('mdx', 'noise_floor_duration_ms')
            self.mdx_onset_snr_threshold = self._config.getfloat('mdx', 'onset_snr_threshold')
            self.mdx_onset_abs_threshold = self._config.getfloat('mdx', 'onset_abs_threshold')
            self.mdx_min_voiced_duration_ms = self._config.getint('mdx', 'min_voiced_duration_ms')
            self.mdx_hysteresis_ms = self._config.getint('mdx', 'hysteresis_ms')
            # Expanding search parameters
            self.mdx_initial_radius_ms = self._config.getint('mdx', 'initial_radius_ms')
            self.mdx_radius_increment_ms = self._config.getint('mdx', 'radius_increment_ms')
            self.mdx_max_expansions = self._config.getint('mdx', 'max_expansions')
            # Performance optimizations
            self.mdx_use_fp16 = self._config.getboolean('mdx', 'use_fp16')
            self.mdx_resample_hz = self._config.getint('mdx', 'resample_hz')
            self.mdx_early_stop_tolerance_ms = self._config.getint('mdx', 'early_stop_tolerance_ms')
            self.mdx_tf32 = self._config.getboolean('mdx', 'tf32')
            # Confidence and preview
            self.mdx_confidence_threshold = self._config.getfloat('mdx', 'confidence_threshold')
            self.mdx_preview_pre_ms = self._config.getint('mdx', 'preview_pre_ms')
            self.mdx_preview_post_ms = self._config.getint('mdx', 'preview_post_ms')

        # General
        self.log_level_str = self._config.get('General', 'log_level')
        self.log_level = self._get_log_level(self.log_level_str)

        # GPU Pack settings
        self.gpu_opt_in = self._config.getboolean('General', 'gpu_opt_in', fallback=False)
        self.gpu_flavor = self._config.get('General', 'gpu_flavor', fallback='cu121')
        self.gpu_pack_installed_version = self._config.get('General', 'gpu_pack_installed_version', fallback='')
        self.gpu_pack_path = self._config.get('General', 'gpu_pack_path', fallback='')
        self.gpu_last_health = self._config.get('General', 'gpu_last_health', fallback='')
        self.gpu_last_error = self._config.get('General', 'gpu_last_error', fallback='')
        self.gpu_pack_dialog_dont_show = self._config.getboolean('General', 'gpu_pack_dialog_dont_show', fallback=False)
        self.prefer_system_pytorch = self._config.getboolean('General', 'prefer_system_pytorch', fallback=True)

        # Window geometry
        self.window_width = self._config.getint('Window', 'width', fallback=1024)
        self.window_height = self._config.getint('Window', 'height', fallback=768)
        self.window_x = self._config.getint('Window', 'x', fallback=-1)
        self.window_y = self._config.getint('Window', 'y', fallback=-1)
        self.window_maximized = self._config.getboolean('Window', 'maximized', fallback=False)

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
        """Save current configuration to file"""
        # Update config object with current property values
        # Only save last_directory if it's not empty (preserve user's selection)
        if self.last_directory:
            self._config['Paths']['last_directory'] = self.last_directory

        # GPU Pack settings
        self._config['General']['gpu_opt_in'] = 'true' if self.gpu_opt_in else 'false'
        self._config['General']['gpu_flavor'] = self.gpu_flavor
        self._config['General']['gpu_pack_installed_version'] = self.gpu_pack_installed_version
        self._config['General']['gpu_pack_path'] = self.gpu_pack_path
        self._config['General']['gpu_last_health'] = self.gpu_last_health
        self._config['General']['gpu_last_error'] = self.gpu_last_error
        self._config['General']['gpu_pack_dialog_dont_show'] = 'true' if self.gpu_pack_dialog_dont_show else 'false'
        self._config['General']['prefer_system_pytorch'] = 'true' if self.prefer_system_pytorch else 'false'

        # Window geometry
        self._config['Window']['width'] = str(self.window_width)
        self._config['Window']['height'] = str(self.window_height)
        self._config['Window']['x'] = str(self.window_x)
        self._config['Window']['y'] = str(self.window_y)
        self._config['Window']['maximized'] = 'true' if self.window_maximized else 'false'

        # Write to file
        with open(self.config_path, 'w') as configfile:
            self._config.write(configfile)

        logger.debug(f"Configuration saved to {self.config_path}")

    def save_config(self):
        """Alias for save() to match bootstrap expectations"""
        self.save()

    def log_config_location(self):
        """Log the configuration file location (call after logging is set up)"""
        print(f"Configuration loaded from: {self.config_path}")
        logger.info(f"Configuration loaded from: {self.config_path}")
