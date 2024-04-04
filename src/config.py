import os
from PyQt6.QtCore import QObject

class Config(QObject):

    tmp_root = os.path.join("..", ".tmp")
        
    # Directory where the songs are located
    default_directory = os.path.join("..", "samples")
    #_directory: str = "Z:\\UltraStarDeluxe\\Songs\\usdb.animux.de"

    # Detection time in seconds
    default_detection_time: int = 30

    # Maximum gap tolerance in milliseconds
    gap_tolerance: int = 500

    detected_gap_color = "blue"
    playback_position_color = "red"
    waveform_color = "gray"

    adjust_player_position_step_audio = 100
    adjust_player_position_step_vocals = 10

    spleeter = True