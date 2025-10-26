"""
Gap Marker Color Constants

Defines consistent colors for gap markers across waveform and UI buttons.
"""

from PySide6.QtGui import QColor

# Waveform marker colors
PLAYHEAD_COLOR = QColor(255, 0, 0)  # Red - current playback position (for "Save play position")
DETECTED_GAP_COLOR = QColor(0, 120, 255)  # Blue - AI-detected gap
REVERT_GAP_COLOR = QColor(128, 128, 128)  # Gray - original gap from file (for revert)

# Color hex strings for button styling
PLAYHEAD_HEX = "#FF0000"  # Red
DETECTED_GAP_HEX = "#0078FF"  # Blue
REVERT_GAP_HEX = "#808080"  # Gray