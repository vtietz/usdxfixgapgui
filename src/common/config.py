import os
import sys
import configparser
from PySide6.QtCore import QObject

# Import the resource_path function from the main script
try:
    from usdxfixgap import resource_path
except ImportError:
    # Fallback implementation if we can't import
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
        
        # Try to load from config file
        config_path = resource_path('config.ini')
        if os.path.exists(config_path):
            self._config.read(config_path)
        else:
            print(f"Warning: Configuration file not found at {config_path}, using defaults")
        
        # Initialize properties from config values
        self._initialize_properties()
    
    def _set_defaults(self):
        """Set default configuration values"""
        self._config['Paths'] = {
            'tmp_root': '../.tmp',
            'default_directory': '../samples'
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