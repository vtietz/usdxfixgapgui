"""
BottomActionBar - Sticky action bar for gap editing workflow.

Three clusters:
- Left: Gap editing (current gap input, apply detected, revert)
- Center: Transport controls (play/pause, jump to current, jump to detected)
- Right: Commit actions (save, keep original)
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QSpinBox, QFrame
)
from PySide6.QtCore import Signal, Qt
from typing import Optional


class BottomActionBar(QWidget):
    """
    Sticky action bar for gap editing operations.

    Left cluster:
        - Current gap spin box (ms)
        - Apply detected button
        - Revert button

    Center cluster:
        - Play/Pause button
        - Jump to current gap button
        - Jump to detected gap button

    Right cluster:
        - Save button
        - Keep original button

    Signals:
        current_gap_changed: Emitted when user changes current gap value (int: ms)
        apply_detected_clicked: Emitted when apply detected button clicked
        revert_clicked: Emitted when revert button clicked
        play_pause_clicked: Emitted when play/pause button clicked
        jump_to_current_clicked: Emitted when jump to current button clicked
        jump_to_detected_clicked: Emitted when jump to detected button clicked
        save_clicked: Emitted when save button clicked
        keep_original_clicked: Emitted when keep original button clicked
    """

    # Left cluster
    current_gap_changed = Signal(int)
    apply_detected_clicked = Signal()
    revert_clicked = Signal()

    # Center cluster
    play_pause_clicked = Signal()
    jump_to_current_clicked = Signal()
    jump_to_detected_clicked = Signal()

    # Right cluster
    save_clicked = Signal()
    keep_original_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._is_playing = False
        self._has_detected_gap = False
        self._is_dirty = False

        self._setup_ui()
        self._apply_styles()
        self._update_button_states()

    def _setup_ui(self):
        """Create the action bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(16)

        # Left cluster: Gap editing
        left_cluster = self._create_left_cluster()

        # Center cluster: Transport
        center_cluster = self._create_center_cluster()

        # Right cluster: Commit
        right_cluster = self._create_right_cluster()

        # Add clusters with stretches
        layout.addLayout(left_cluster)
        layout.addStretch()
        layout.addLayout(center_cluster)
        layout.addStretch()
        layout.addLayout(right_cluster)

    def _create_left_cluster(self) -> QHBoxLayout:
        """Create gap editing cluster."""
        layout = QHBoxLayout()
        layout.setSpacing(8)

        # Current gap label and spin box
        gap_label = QLabel("Current Gap:")

        self.gap_spinbox = QSpinBox()
        self.gap_spinbox.setRange(0, 999999)
        self.gap_spinbox.setSuffix(" ms")
        self.gap_spinbox.setFixedWidth(100)
        self.gap_spinbox.valueChanged.connect(self.current_gap_changed)

        # Apply detected button
        self.apply_detected_btn = QPushButton("Apply Detected")
        self.apply_detected_btn.setToolTip("Apply AI-detected gap value (A)")
        self.apply_detected_btn.clicked.connect(self.apply_detected_clicked)

        # Revert button
        self.revert_btn = QPushButton("Revert")
        self.revert_btn.setToolTip("Revert to saved value (R)")
        self.revert_btn.clicked.connect(self.revert_clicked)

        layout.addWidget(gap_label)
        layout.addWidget(self.gap_spinbox)
        layout.addWidget(self.apply_detected_btn)
        layout.addWidget(self.revert_btn)

        return layout

    def _create_center_cluster(self) -> QHBoxLayout:
        """Create transport controls cluster."""
        layout = QHBoxLayout()
        layout.setSpacing(8)

        # Play/Pause button
        self.play_pause_btn = QPushButton("Play")
        self.play_pause_btn.setCheckable(True)
        self.play_pause_btn.setToolTip("Play/Pause (Space)")
        self.play_pause_btn.clicked.connect(self.play_pause_clicked)

        # Jump to current gap
        self.jump_current_btn = QPushButton("→ Current Gap")
        self.jump_current_btn.setToolTip("Jump to current gap position (G)")
        self.jump_current_btn.clicked.connect(self.jump_to_current_clicked)

        # Jump to detected gap
        self.jump_detected_btn = QPushButton("→ Detected Gap")
        self.jump_detected_btn.setToolTip("Jump to detected gap position (D)")
        self.jump_detected_btn.clicked.connect(self.jump_to_detected_clicked)

        layout.addWidget(self.play_pause_btn)
        layout.addWidget(self.jump_current_btn)
        layout.addWidget(self.jump_detected_btn)

        return layout

    def _create_right_cluster(self) -> QHBoxLayout:
        """Create commit actions cluster."""
        layout = QHBoxLayout()
        layout.setSpacing(8)

        # Save button
        self.save_btn = QPushButton("Save")
        self.save_btn.setToolTip("Save current gap value (S)")
        self.save_btn.clicked.connect(self.save_clicked)

        # Keep original button
        self.keep_original_btn = QPushButton("Keep Original")
        self.keep_original_btn.setToolTip("Revert to original and mark as solved")
        self.keep_original_btn.clicked.connect(self.keep_original_clicked)

        layout.addWidget(self.save_btn)
        layout.addWidget(self.keep_original_btn)

        return layout

    def _apply_styles(self):
        """Apply styling to action bar."""
        # Dark theme with professional button styling
        style = """
            QWidget {
                background-color: #1e1e1e;
                border-top: 1px solid #3a3a3a;
            }
            QPushButton {
                background-color: #2b2b2b;
                border: 1px solid #555;
                color: #ccc;
                padding: 8px 16px;
                border-radius: 3px;
                font-size: 13px;
                min-height: 32px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border: 1px solid #666;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #555;
                border: 1px solid #333;
            }
            QPushButton:checked {
                background-color: #0e639c;
                color: white;
                border: 1px solid #1177bb;
                font-weight: bold;
            }
            QLabel {
                color: #ccc;
                font-size: 13px;
            }
            QSpinBox {
                background-color: #2b2b2b;
                border: 1px solid #555;
                color: #ccc;
                padding: 6px 8px;
                border-radius: 3px;
                font-size: 13px;
                min-height: 32px;
            }
            QSpinBox:focus {
                border: 1px solid #1177bb;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 16px;
                background-color: #2b2b2b;
                border: 1px solid #555;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #3a3a3a;
            }
        """
        self.setStyleSheet(style)

    def _update_button_states(self):
        """Update button enabled states based on current state."""
        # Apply detected: enabled if detected gap available
        self.apply_detected_btn.setEnabled(self._has_detected_gap)

        # Revert: enabled if dirty
        self.revert_btn.setEnabled(self._is_dirty)

        # Jump to detected: enabled if detected gap available
        self.jump_detected_btn.setEnabled(self._has_detected_gap)

        # Save: enabled if dirty
        self.save_btn.setEnabled(self._is_dirty)

    def set_current_gap(self, gap_ms: int):
        """
        Set the current gap value.

        Args:
            gap_ms: Gap value in milliseconds
        """
        # Block signals to avoid triggering change event
        self.gap_spinbox.blockSignals(True)
        self.gap_spinbox.setValue(gap_ms)
        self.gap_spinbox.blockSignals(False)

    def set_has_detected_gap(self, has_detected: bool):
        """
        Update whether a detected gap is available.

        Args:
            has_detected: True if detected gap available
        """
        self._has_detected_gap = has_detected
        self._update_button_states()

    def set_is_dirty(self, is_dirty: bool):
        """
        Update dirty state.

        Args:
            is_dirty: True if current gap differs from saved
        """
        self._is_dirty = is_dirty
        self._update_button_states()

    def set_is_playing(self, is_playing: bool):
        """
        Update play/pause button state.

        Args:
            is_playing: True if audio is playing
        """
        self._is_playing = is_playing
        self.play_pause_btn.setChecked(is_playing)
        self.play_pause_btn.setText("Pause" if is_playing else "Play")
