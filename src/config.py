import os
from PySide6.QtCore import QObject

class Config(QObject):

    # Temporary directory for vocal files and waveform images
    tmp_root = os.path.join("..", ".tmp")
        
    # Directory where the songs are located
    default_directory: str = os.path.join("..", "samples")

    # Detection time in seconds
    default_detection_time: int = 30

    # Maximum gap tolerance in milliseconds
    gap_tolerance: int = 500

    # Colors
    detected_gap_color = "blue"
    playback_position_color = "red"
    waveform_color = "gray"
    silence_periods_color = (105, 105, 105, 128)

    # Steps when pressing the arrow keys in the player
    adjust_player_position_step_audio = 100
    adjust_player_position_step_vocals = 10

    # use spleeter
    spleeter = True

    # ffmpeg parameters for silence detection
    silence_detect_params = "silencedetect=noise=-30dB:d=0.2"