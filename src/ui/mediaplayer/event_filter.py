from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, QEvent, Qt


class MediaPlayerEventFilter(QObject):
    def __init__(self, component, callback_left, callback_right, callback_play):
        super().__init__()
        self.callback_left = callback_left
        self.callback_right = callback_right
        self.callback_play = callback_play
        self.component = component

    def eventFilter(self, watched, event):
        widget = QApplication.focusWidget()
        while widget is not None:
            if widget == self.component:
                if event.type() == QEvent.Type.KeyPress:
                    if event.key() == Qt.Key.Key_Left:
                        self.callback_left()
                        return True
                    elif event.key() == Qt.Key.Key_Right:
                        self.callback_right()
                        return True
                    elif event.key() == Qt.Key.Key_Space:
                        self.callback_play()
                        return True
                return False
            widget = widget.parent()

        return False  # Event not handled, continue with default processing
