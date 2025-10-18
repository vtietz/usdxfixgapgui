"""
Live log viewer widget for the main window.

Displays log messages from the application log file in real-time with scrollable history.
"""

import logging
import os
from collections import deque
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel, QSizePolicy
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QTextCursor

logger = logging.getLogger(__name__)


class LogViewerWidget(QWidget):
    """
    Widget that displays log messages from the log file.
    Updates periodically to show new log entries with full scrollable history.
    """

    def __init__(self, log_file_path: str, max_lines: int = 1000, parent=None):
        """
        Initialize the log viewer.

        Args:
            log_file_path: Path to the log file to monitor
            max_lines: Maximum number of lines to keep in buffer (default: 1000)
            parent: Optional parent widget
        """
        super().__init__(parent)
        self.log_file_path = log_file_path
        self.max_lines = max_lines
        # Start from current end of file (skip old logs from previous sessions)
        try:
            self.last_position = os.path.getsize(log_file_path) if os.path.exists(log_file_path) else 0
        except Exception:
            self.last_position = 0
        self.log_lines = deque(maxlen=max_lines)  # Ring buffer for log lines

        self._init_ui()
        self._start_update_timer()

    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Header label
        header = QLabel("Application Logs")
        header_font = QFont()
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # Text edit for log display
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMinimumHeight(80)   # Minimum height for visibility
        self.text_edit.setMaximumHeight(150)  # Allow more space for scrolling
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Disable line wrapping to enable horizontal scrolling
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Use monospace font with medium weight for better readability
        font = QFont("Consolas", 9)  # Slightly larger font (9 instead of 8)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        font.setWeight(QFont.Weight.Medium)  # Medium weight - bolder than normal, not too heavy
        self.text_edit.setFont(font)

        # Style the text edit with dark theme matching VS Code
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #3C3C3C;
                border-radius: 3px;
                padding: 4px;
            }
        """)

        layout.addWidget(self.text_edit)

        # Set widget size policy - allow vertical expansion
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def _start_update_timer(self):
        """Start timer to periodically check for new log entries."""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_log_display)
        self.update_timer.start(500)  # Update every 500ms

    def _update_log_display(self):
        """Read new log lines and update the display."""
        if not os.path.exists(self.log_file_path):
            return

        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Seek to last known position
                f.seek(self.last_position)

                # Read new lines
                new_lines = f.readlines()

                # Update position for next read
                self.last_position = f.tell()

                # Add new lines to buffer
                for line in new_lines:
                    line = line.rstrip('\n')
                    if line:  # Skip empty lines
                        self.log_lines.append(line)

                # Update display if we got new lines
                if new_lines:
                    self._refresh_display()

        except Exception as e:
            # Silently ignore errors (file might be locked, etc.)
            pass

    def _refresh_display(self):
        """Refresh the text display with current log lines."""
        # Remember current scroll position
        scrollbar = self.text_edit.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 10

        # Build display text with enhanced color coding
        display_text = []

        for line in self.log_lines:
            # Enhanced color coding based on log level with better formatting
            # Match VS Code-like log colors from the screenshot
            if ' ERROR ' in line or ' CRITICAL ' in line:
                # Red for errors
                colored_line = f'<span style="color: #F48771; font-weight: 500;">{self._html_escape(line)}</span>'
            elif ' WARNING ' in line:
                # Yellow/orange for warnings
                colored_line = f'<span style="color: #D7BA7D;">{self._html_escape(line)}</span>'
            elif ' INFO ' in line:
                # Bright cyan/blue for info (like in screenshot)
                colored_line = f'<span style="color: #4EC9B0;">{self._html_escape(line)}</span>'
            elif ' DEBUG ' in line:
                # Green for debug messages
                colored_line = f'<span style="color: #6A9955;">{self._html_escape(line)}</span>'
            else:
                # Default gray color for other messages
                colored_line = f'<span style="color: #D4D4D4;">{self._html_escape(line)}</span>'

            display_text.append(colored_line)

        # Update text edit with proper HTML formatting
        # Use <pre> tag to preserve spacing and enable horizontal scroll
        html_content = '<pre style="margin: 0; padding: 0; font-family: inherit;">' + '<br>'.join(display_text) + '</pre>'
        self.text_edit.setHtml(html_content)

        # Auto-scroll to bottom only if we were already at bottom
        # OR if the scrollbar maximum was 0 (empty/first load)
        # This preserves manual scroll position for reviewing history
        if was_at_bottom or scrollbar.maximum() == 0:
            # Use QTimer to ensure scroll happens AFTER HTML is rendered
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._scroll_to_bottom())

    def _scroll_to_bottom(self):
        """Scroll to the bottom of the log display."""
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)
        # Also explicitly set scrollbar to maximum
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @staticmethod
    def _html_escape(text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))

    def cleanup(self):
        """Stop the update timer."""
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
