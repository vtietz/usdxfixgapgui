import os
import logging
from PySide6.QtWidgets import QLabel, QWidget, QSizePolicy
from PySide6.QtGui import QPainter, QPen, QPixmap, QColor
from PySide6.QtCore import Qt, Signal, QEvent
from ui.mediaplayer.gap_marker_colors import PLAYHEAD_COLOR, DETECTED_GAP_COLOR, REVERT_GAP_COLOR
from utils.time_position import time_to_pixel, time_to_normalized_position

logger = logging.getLogger(__name__)


class WaveformWidget(QLabel):
    # Change signal type to float
    position_clicked = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("padding: 0px; margin: 0px;")
        self.setMinimumHeight(100)  # Minimum height instead of fixed
        self.setScaledContents(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)  # Allow vertical expansion
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Placeholder text state
        self.placeholder_text = ""
        self.placeholder_visible = False

        # Markers visibility state
        self.markers_visible = True  # Hide markers when player disabled or no media

        # Overlay for showing the current play position
        self.overlay = QWidget(self)
        self.overlay.setFixedSize(self.size())
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Allow clicks to pass through
        self.overlay.paintEvent = self.paint_overlay

        self.currentPosition = 0

        # Track B: Gap markers
        self.duration_ms = 0  # Current media duration (vocals or audio)
        self.original_audio_duration_ms = 0  # Original audio duration (for gap markers and position mapping)
        self.original_gap_ms = None  # Original gap marker (orange)
        self.current_gap_ms = None  # Current gap marker (blue)
        self.detected_gap_ms = None  # Detected gap marker (green)

        self.installEventFilter(self)

    def paint_overlay(self, event):
        """Draw playhead and gap markers on waveform."""
        if not self.markers_visible:
            return  # Skip drawing markers when disabled

        painter = QPainter(self.overlay)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        overlay_width = self.overlay.width()
        overlay_height = self.overlay.height()

        # 1. Draw playhead (red, solid, thin)
        pen = QPen(PLAYHEAD_COLOR, 2)
        painter.setPen(pen)
        playhead_x = int(self.currentPosition * overlay_width)
        painter.drawLine(playhead_x, 0, playhead_x, overlay_height)

        # 2. Draw gap markers if duration is known
        # Gap markers represent absolute time positions (milliseconds) that should appear
        # at the same time position on both audio and vocals waveforms.
        # Use current waveform duration for positioning (not original_audio_duration).
        if self.duration_ms > 0:
            # Draw revert/original gap marker (gray, dashed)
            if self.original_gap_ms is not None:
                # Map absolute time (ms) to pixel position on current waveform
                original_x = time_to_pixel(self.original_gap_ms, self.duration_ms, overlay_width)
                pen = QPen(REVERT_GAP_COLOR, 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawLine(original_x, 0, original_x, overlay_height)

            # Draw detected gap marker (green, solid, thicker)
            if self.detected_gap_ms is not None:
                # Map absolute time (ms) to pixel position on current waveform
                detected_x = time_to_pixel(self.detected_gap_ms, self.duration_ms, overlay_width)
                pen = QPen(DETECTED_GAP_COLOR, 3)
                painter.setPen(pen)
                painter.drawLine(detected_x, 0, detected_x, overlay_height)

        painter.end()

    def set_placeholder(self, text: str):
        """Set placeholder text to display when waveform is not available"""
        self.placeholder_text = text
        self.placeholder_visible = True
        self.update()  # Trigger repaint

    def clear_placeholder(self):
        """Clear placeholder text"""
        self.placeholder_text = ""
        self.placeholder_visible = False
        self.update()  # Trigger repaint

    def set_markers_visible(self, visible: bool):
        """Control marker visibility (hide when player disabled or no media)"""
        self.markers_visible = visible
        self.overlay.update()  # Trigger marker overlay repaint

    def paintEvent(self, arg__1):
        """Custom paint event to draw placeholder text when visible"""
        # Draw the pixmap first (standard QLabel behavior)
        super().paintEvent(arg__1)

        # Draw placeholder text if visible
        if self.placeholder_visible and self.placeholder_text:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Use default application font (matches buttons)
            font = self.font()
            painter.setFont(font)

            # Calculate text bounding box
            text_rect = painter.fontMetrics().boundingRect(self.placeholder_text)

            # Calculate center position
            widget_rect = self.rect()
            text_x = (widget_rect.width() - text_rect.width()) // 2
            text_y = (widget_rect.height() - text_rect.height()) // 2 + text_rect.height()

            # Draw text in a subtle gray color (no background)
            painter.setPen(QColor(160, 160, 160))  # Medium gray for subtle appearance
            painter.drawText(text_x, text_y, self.placeholder_text)

            painter.end()

    def update_position(self, position, duration):
        """Update playhead position without affecting gap marker duration.

        Args:
            position: Current playback position in milliseconds
            duration: Current media duration in milliseconds (for playhead normalization only)
        """
        self.currentPosition = time_to_normalized_position(position, duration)
        self.overlay.update()  # Trigger a repaint

    def set_gap_markers(self, original_gap_ms=None, detected_gap_ms=None):
        """
        Set gap marker positions for display.

        Args:
            original_gap_ms: Original/revert gap position in milliseconds (gray dashed marker)
            detected_gap_ms: AI-detected gap position in milliseconds (green solid marker)
        """
        logger.debug(
            f"[MARKER DEBUG] set_gap_markers() called: original={original_gap_ms}, detected={detected_gap_ms}, "
            f"current duration_ms={self.duration_ms}"
        )
        self.original_gap_ms = original_gap_ms
        self.detected_gap_ms = detected_gap_ms
        self.overlay.update()  # Trigger repaint to show markers
        self.update()  # Also update the main widget to ensure proper sync

    def set_original_audio_duration(self, duration_ms: int):
        """Set the original audio duration for correct timeline mapping in vocals mode.

        Args:
            duration_ms: Duration of the original audio file in milliseconds
        """
        self.original_audio_duration_ms = duration_ms
        logger.debug(f"Original audio duration set to {duration_ms}ms for timeline mapping")

    def load_waveform(self, file: str | None):
        if file and os.path.exists(file):
            self.setPixmap(QPixmap(file))
            self.clear_placeholder()  # Clear placeholder when waveform loads
            self.set_markers_visible(True)  # Restore markers when media loaded
        else:
            self.setPixmap(QPixmap())
            self.set_markers_visible(False)  # Hide markers when no media
            # Don't clear placeholder here - let caller set appropriate message

    def mousePressEvent(self, ev):
        # Ensure parent gets focus
        p = self.parent()
        if isinstance(p, QWidget):
            p.setFocus()

        # Calculate position based on click
        click_position = ev.position().x()
        widget_width = self.width()

        # Safeguard against division by zero
        if widget_width > 0:
            # Click position is relative to the current waveform (0.0 to 1.0)
            # This directly maps to the current media file (audio or vocals)
            relative_position = max(0.0, min(1.0, click_position / widget_width))
            self.position_clicked.emit(relative_position)

        # Let the event continue processing
        super().mousePressEvent(ev)

    def eventFilter(self, watched, event):
        if watched == self and event.type() == QEvent.Type.Resize:
            # Adjust the overlay size to match the waveformLabel
            self.overlay.setFixedSize(self.size())
        return super().eventFilter(watched, event)
