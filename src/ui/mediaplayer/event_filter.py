from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit, QPlainTextEdit
from PySide6.QtCore import QObject, QEvent, Qt


class MediaPlayerEventFilter(QObject):
    def __init__(self, component, callback_left, callback_right, callback_play):
        super().__init__()
        self.callback_left = callback_left
        self.callback_right = callback_right
        self.callback_play = callback_play
        self.component = component

    def eventFilter(self, watched, event):
        if event.type() != QEvent.Type.KeyPress:
            return False

        # Check if we're in a text input field where arrow keys should navigate text
        widget = QApplication.focusWidget()
        if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            return False  # Let text inputs handle their own arrow keys

        # Handle media player shortcuts globally (unless in text input)
        if event.key() == Qt.Key.Key_Left:
            self.callback_left()
            return True
        elif event.key() == Qt.Key.Key_Right:
            self.callback_right()
            return True
        elif event.key() == Qt.Key.Key_Space:
            # Space is more context-sensitive - only handle if media player has focus
            # or if we're not in any interactive widget
            widget = QApplication.focusWidget()
            while widget is not None:
                if widget == self.component:
                    self.callback_play()
                    return True
                widget = widget.parent()

        return False  # Event not handled, continue with default processing
