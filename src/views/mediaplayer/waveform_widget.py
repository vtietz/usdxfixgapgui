import os
from PySide6.QtWidgets import QLabel, QWidget, QSizePolicy
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtCore import Qt, Signal, QEvent

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
        
        # Overlay for showing the current play position
        self.overlay = QWidget(self)
        self.overlay.setFixedSize(self.size())
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Allow clicks to pass through
        self.overlay.paintEvent = self.paint_overlay
        
        self.currentPosition = 0
        self.installEventFilter(self)
        
    def paint_overlay(self, event):
        painter = QPainter(self.overlay)
        pen = QPen(Qt.GlobalColor.red, 2)
        painter.setPen(pen)
        # Convert x to an integer to ensure it matches the expected argument type
        x = int(self.currentPosition * self.overlay.width())
        painter.drawLine(x, 0, x, self.overlay.height())
    
    def update_position(self, position, duration):
        if duration > 0:
            self.currentPosition = position / duration
            self.overlay.update()  # Trigger a repaint
        else:
            self.currentPosition = 0
            
    def load_waveform(self, file: str):
        if file and os.path.exists(file):
            self.setPixmap(QPixmap(file))
        else:
            self.setPixmap(QPixmap())
            
    def mousePressEvent(self, event):
        # Ensure parent gets focus
        if self.parent():
            self.parent().setFocus()
        
        # Calculate position based on click
        click_position = event.position().x()
        widget_width = self.width()
        
        # Safeguard against division by zero
        if widget_width > 0:
            relative_position = max(0.0, min(1.0, click_position / widget_width))  # Ensure float division
            self.position_clicked.emit(relative_position)
        
        # Let the event continue processing
        super().mousePressEvent(event)
        
    def eventFilter(self, watched, event):
        if watched == self and event.type() == QEvent.Type.Resize:
            # Adjust the overlay size to match the waveformLabel
            self.overlay.setFixedSize(self.size())
        return super().eventFilter(watched, event)
