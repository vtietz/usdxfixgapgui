import os
import sys
import configparser
import logging
from PySide6.QtCore import QObject
from utils.files import get_app_dir

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
        config_path = os.path.join(get_app_dir(), 'config.ini')
        
        if not os.path.exists(config_path):
            logger.info(f"Config file not found. Creating default config at: {config_path}")
            
            # Create output directory if it doesn't exist
            output_dir = os.path.join(get_app_dir(), 'output')
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.info(f"Created output directory: {output_dir}")
            
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
            'tmp_root': os.path.join(get_app_dir(), '.tmp'),
            'default_directory': os.path.join(get_app_dir(), 'samples'),
            'last_directory': ''  # New parameter for last used directory
        }
        
        self._config['Detection'] = {
            'default_detection_time': '30',
            'gap_tolerance': '500'
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
            'method': 'vad_preview',  # Options: spleeter, vad_preview, hq_segment
            'normalization_level': '-20',  # Default normalization level is -20 dB
            'auto_normalize': 'false'      # Default is not to auto-normalize
        }
        
        # Spleeter-specific settings
        self._config['spleeter'] = {
            'silence_detect_params': 'silencedetect=noise=-30dB:d=0.2'
        }
        
        # VAD Preview settings (new default method)
        self._config['vad_preview'] = {
            'preview_pre_ms': '3000',
            'preview_post_ms': '9000',
            'vad_frame_ms': '30',
            'vad_min_speech_ms': '120',
            'vad_min_silence_ms': '200',
            'flux_snap_window_ms': '150',
            'flux_snap_enabled': 'true',  # Enable spectral flux snapping for onset refinement
            'vad_aggressiveness': '3'  # WebRTC VAD: 0-3, higher = more aggressive
        }
        
        # HQ Segment settings (on-demand high-quality re-analysis)
        self._config['hq_segment'] = {
            'hq_reanalyze_threshold': '0.6',
            'hq_model': 'mdx_small',  # Options: mdx_small, demucs_segment
            'preview_pre_ms': '3000',
            'preview_post_ms': '9000'
        }
        
        self._config['General'] = {
            'DefaultOutputPath': os.path.join(get_app_dir(), 'output'),
            'LogLevel': 'INFO'
        }
        
        self._config['Audio'] = {
            'DefaultVolume': '0.5',
            'AutoPlay': 'False'
        }

    def _initialize_properties(self):
        """Initialize class properties from config values"""
        # Paths
        self.tmp_root = self._config.get('Paths', 'tmp_root')
        self.default_directory = self._config.get('Paths', 'default_directory')
        self.last_directory = self._config.get('Paths', 'last_directory')
        
        # Detection
        self.default_detection_time = self._config.getint('Detection', 'default_detection_time')
        self.gap_tolerance = self._config.getint('Detection', 'gap_tolerance')
        
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
        
        # Spleeter settings
        self.spleeter_silence_detect_params = self._config.get('spleeter', 'silence_detect_params')
        
        # VAD Preview settings
        self.vad_preview_pre_ms = self._config.getint('vad_preview', 'preview_pre_ms')
        self.vad_preview_post_ms = self._config.getint('vad_preview', 'preview_post_ms')
        self.vad_frame_ms = self._config.getint('vad_preview', 'vad_frame_ms')
        self.vad_min_speech_ms = self._config.getint('vad_preview', 'vad_min_speech_ms')
        self.vad_min_silence_ms = self._config.getint('vad_preview', 'vad_min_silence_ms')
        self.flux_snap_window_ms = self._config.getint('vad_preview', 'flux_snap_window_ms')
        self.flux_snap_enabled = self._config.getboolean('vad_preview', 'flux_snap_enabled')
        self.vad_aggressiveness = self._config.getint('vad_preview', 'vad_aggressiveness')
        
        # HQ Segment settings
        self.hq_reanalyze_threshold = self._config.getfloat('hq_segment', 'hq_reanalyze_threshold')
        self.hq_model = self._config.get('hq_segment', 'hq_model')
        self.hq_preview_pre_ms = self._config.getint('hq_segment', 'preview_pre_ms')
        self.hq_preview_post_ms = self._config.getint('hq_segment', 'preview_post_ms')
        
        # General
        self.log_level_str = self._config.get('General', 'LogLevel')
        self.log_level = self._get_log_level(self.log_level_str)
        
        # Backward compatibility - set spleeter flag based on method
        self.spleeter = (self.method == 'spleeter')

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
        self._config['Paths']['last_directory'] = self.last_directory
        
        # Write to file
        with open(self.config_path, 'w') as configfile:
            self._config.write(configfile)
        
        logger.debug(f"Configuration saved to {self.config_path}")