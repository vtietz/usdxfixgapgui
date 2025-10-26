import os
from PySide6.QtWidgets import QLabel, QWidget, QSizePolicy
from PySide6.QtGui import QPainter, QPen, QPixmap, QColor
from PySide6.QtCore import Qt, Signal, QEvent
from ui.mediaplayer.gap_marker_colors import (
    PLAYHEAD_COLOR, DETECTED_GAP_COLOR, REVERT_GAP_COLOR
)

class WaveformWidget(QLabel):
    # Change signal type to float
    position_clicked = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("padding: 0px; margin: 0px;")
        self.setFixedHeight(150)  # Set a fixed height for the waveform display area
        self.setScaledContents(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Placeholder text state
        self.placeholder_text = ""
        self.placeholder_visible = False

        # Overlay for showing the current play position
        self.overlay = QWidget(self)
        self.overlay.setFixedSize(self.size())
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Allow clicks to pass through
        self.overlay.paintEvent = self.paint_overlay

        self.currentPosition = 0

        # Track B: Gap markers
        self.duration_ms = 0  # Total duration for gap position calculation
        self.original_gap_ms = None  # Original gap marker (orange)
        self.current_gap_ms = None  # Current gap marker (blue)
        self.detected_gap_ms = None  # Detected gap marker (green)

        self.installEventFilter(self)

    def paint_overlay(self, event):
        """Draw playhead and gap markers on waveform."""
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
        if self.duration_ms > 0:
            # Draw revert/original gap marker (gray, dashed, decent)
            if self.original_gap_ms is not None:
                original_x = int((self.original_gap_ms / self.duration_ms) * overlay_width)
                pen = QPen(REVERT_GAP_COLOR, 2, Qt.PenStyle.DashLine)  # Gray dashed
                painter.setPen(pen)
                painter.drawLine(original_x, 0, original_x, overlay_height)

            # Draw detected gap marker (green, solid, visible)
            if self.detected_gap_ms is not None:
                detected_x = int((self.detected_gap_ms / self.duration_ms) * overlay_width)
                pen = QPen(DETECTED_GAP_COLOR, 3)  # Green solid, thicker
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
        if duration > 0:
            self.currentPosition = position / duration
            self.duration_ms = duration  # Track B: Store duration for gap markers
            self.overlay.update()  # Trigger a repaint
        else:
            self.currentPosition = 0
            self.duration_ms = 0

    def set_gap_markers(self, original_gap_ms=None, detected_gap_ms=None):
        """
        Set gap marker positions for display.

        Args:
            original_gap_ms: Original/revert gap position in milliseconds (gray dashed marker)
            detected_gap_ms: AI-detected gap position in milliseconds (green solid marker)
        """
        self.original_gap_ms = original_gap_ms
        self.detected_gap_ms = detected_gap_ms
        self.overlay.update()  # Trigger repaint to show markers

    def load_waveform(self, file: str | None):
        if file and os.path.exists(file):
            self.setPixmap(QPixmap(file))
            self.clear_placeholder()  # Clear placeholder when waveform loads
        else:
            self.setPixmap(QPixmap())
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
            relative_position = max(0.0, min(1.0, click_position / widget_width))  # Ensure float division
            self.position_clicked.emit(relative_position)

        # Let the event continue processing
        super().mousePressEvent(ev)

    def eventFilter(self, watched, event):
        if watched == self and event.type() == QEvent.Type.Resize:
            # Adjust the overlay size to match the waveformLabel
            self.overlay.setFixedSize(self.size())
        return super().eventFilter(watched, event)
