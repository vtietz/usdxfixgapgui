"""
TabStrip - Segmented control for audio source selection.

Displays Original/Extracted/Both as flat toggle buttons with active state.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup
from PySide6.QtCore import Signal


class AudioSourceTab:
    """Audio source tab identifiers."""

    ORIGINAL = "original"
    EXTRACTED = "extracted"
    BOTH = "both"  # Future: side-by-side comparison


class TabStrip(QWidget):
    """
    Segmented control for selecting audio source.

    Displays three mutually exclusive buttons:
    - Original: Play original audio file
    - Extracted: Play extracted vocals
    - Both: Play both (future feature)

    Signals:
        source_changed: Emitted when user selects a different source (str: original/extracted/both)
    """

    source_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_source = AudioSourceTab.ORIGINAL
        self._extracted_enabled = False  # Track if extracted vocals available

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """Create the tab strip UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create button group for mutual exclusivity
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        # Create buttons
        self.original_btn = QPushButton("Original")
        self.original_btn.setCheckable(True)
        self.original_btn.setChecked(True)
        self.original_btn.setProperty("tab", AudioSourceTab.ORIGINAL)

        self.extracted_btn = QPushButton("Extracted")
        self.extracted_btn.setCheckable(True)
        self.extracted_btn.setEnabled(False)  # Disabled until vocals available
        self.extracted_btn.setProperty("tab", AudioSourceTab.EXTRACTED)

        self.both_btn = QPushButton("Both")
        self.both_btn.setCheckable(True)
        self.both_btn.setEnabled(False)  # Future feature
        self.both_btn.setProperty("tab", AudioSourceTab.BOTH)

        # Add to button group
        self.button_group.addButton(self.original_btn)
        self.button_group.addButton(self.extracted_btn)
        self.button_group.addButton(self.both_btn)

        # Connect signals
        self.original_btn.clicked.connect(lambda: self._on_tab_clicked(AudioSourceTab.ORIGINAL))
        self.extracted_btn.clicked.connect(lambda: self._on_tab_clicked(AudioSourceTab.EXTRACTED))
        self.both_btn.clicked.connect(lambda: self._on_tab_clicked(AudioSourceTab.BOTH))

        # Add to layout
        layout.addWidget(self.original_btn)
        layout.addWidget(self.extracted_btn)
        layout.addWidget(self.both_btn)

    def _apply_styles(self):
        """Apply flat segmented control styling."""
        # Flat button style with clear active state
        style = """
            QPushButton {
                border: 1px solid #555;
                background-color: #2b2b2b;
                color: #ccc;
                padding: 8px 20px;
                font-size: 13px;
                border-radius: 0;
                min-width: 90px;
                min-height: 34px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #0e639c;
                color: white;
                border: 1px solid #1177bb;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #555;
                border: 1px solid #333;
            }
            QPushButton:first-child {
                border-top-left-radius: 4px;
                border-bottom-left-radius: 4px;
            }
            QPushButton:last-child {
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
        """
        self.setStyleSheet(style)

    def _on_tab_clicked(self, source: str):
        """Handle tab click."""
        if self._current_source != source:
            self._current_source = source
            self.source_changed.emit(source)

    def set_extracted_enabled(self, enabled: bool):
        """
        Enable/disable the Extracted tab.

        Args:
            enabled: True if extracted vocals are available
        """
        self._extracted_enabled = enabled
        self.extracted_btn.setEnabled(enabled)

        # If extracted was selected but now disabled, fall back to original
        if not enabled and self._current_source == AudioSourceTab.EXTRACTED:
            self.original_btn.setChecked(True)
            self._current_source = AudioSourceTab.ORIGINAL
            self.source_changed.emit(AudioSourceTab.ORIGINAL)

    def set_current_source(self, source: str):
        """
        Programmatically set the active source.

        Args:
            source: One of AudioSourceTab.ORIGINAL/EXTRACTED/BOTH
        """
        if source == self._current_source:
            return

        # Validate source is available
        if source == AudioSourceTab.EXTRACTED and not self._extracted_enabled:
            return  # Cannot set to disabled source

        if source == AudioSourceTab.BOTH and not self.both_btn.isEnabled():
            return  # Cannot set to disabled source

        self._current_source = source

        # Update checked state
        if source == AudioSourceTab.ORIGINAL:
            self.original_btn.setChecked(True)
        elif source == AudioSourceTab.EXTRACTED:
            self.extracted_btn.setChecked(True)
        elif source == AudioSourceTab.BOTH:
            self.both_btn.setChecked(True)

    def get_current_source(self) -> str:
        """Get the currently selected source."""
        return self._current_source
