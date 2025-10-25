"""
Gap Marker Color Constants

Defines consistent colors for gap markers across waveform and UI buttons.
"""

from PySide6.QtGui import QColor

# Waveform marker colors
PLAYHEAD_COLOR = QColor(255, 0, 0)  # Red - current playback position
ORIGINAL_GAP_COLOR = QColor(255, 140, 0)  # Orange - original gap from file
CURRENT_GAP_COLOR = QColor(0, 120, 255)  # Blue - current/edited gap
DETECTED_GAP_COLOR = QColor(0, 200, 0)  # Green - AI-detected gap

# Color hex strings for button styling
PLAYHEAD_HEX = "#FF0000"
ORIGINAL_GAP_HEX = "#FF8C00"
CURRENT_GAP_HEX = "#0078FF"
DETECTED_GAP_HEX = "#00C800"
