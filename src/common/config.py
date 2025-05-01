import os
import sys
import configparser
import logging
from PySide6.QtCore import QObject

logger = logging.getLogger(__name__)

def get_app_dir():
    """Get the directory of the executable or script."""
    if hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        return os.path.dirname(sys.executable)
    # Running as a script
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def resource_path(relative_path):
    """Get the absolute path to a resource, works for dev and PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        return os.path.join(sys._MEIPASS, relative_path)
    
    # Check in the application directory first
    app_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    app_path = os.path.join(app_dir, relative_path)
    if os.path.exists(app_path):
        return app_path
        
    # Otherwise check in the current directory
    return os.path.join(os.path.abspath("."), relative_path)

class Config(QObject):
    def __init__(self):
        super().__init__()
        self._config = configparser.ConfigParser()
        
        # Set default values first
        self._set_defaults()
        
        # Ensure config file exists (creates with defaults if it doesn't)
        config_path = self.ensure_config_file_exists()
        
        # Load the config file (either existing or newly created)
        self._config.read(config_path)
        
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
            'default_directory': os.path.join(get_app_dir(), 'samples')
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
            'spleeter': 'true',
            'silence_detect_params': 'silencedetect=noise=-30dB:d=0.2',
            'normalization_level': '-20',  # Default normalization level is -20 dB
            'auto_normalize': 'false'      # Default is not to auto-normalize
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
        self.spleeter = self._config.getboolean('Processing', 'spleeter')
        self.silence_detect_params = self._config.get('Processing', 'silence_detect_params')
        self.normalization_level = self._config.getint('Processing', 'normalization_level')
        self.auto_normalize = self._config.getboolean('Processing', 'auto_normalize')