"""
UI Utility Functions

Helper functions for creating UI elements and visual components.
"""

from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt


def make_color_dot_icon(color_hex: str, diameter: int = 10, outline: bool = False) -> QIcon:
    """Create a small colored circle icon for button indicators.

    This is useful for creating visual legend markers that match waveform
    or chart colors, providing a clear visual link between UI controls
    and their corresponding graphical elements.

    Args:
        color_hex: Hex color string (e.g., "#FF8C00")
        diameter: Icon size in pixels (default: 10)
        outline: Whether to add a subtle border for contrast (default: False)

    Returns:
        QIcon with colored circle, suitable for QPushButton.setIcon()

    Example:
        >>> from ui.ui_utils import make_color_dot_icon
        >>> button = QPushButton("Save gap")
        >>> button.setIcon(make_color_dot_icon("#00C800", diameter=10))
        >>> button.setIconSize(QSize(10, 10))
    """
    pix = QPixmap(diameter, diameter)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    color = QColor(color_hex)
    painter.setBrush(color)

    if outline:
        painter.setPen(QColor("#333"))
    else:
        painter.setPen(Qt.PenStyle.NoPen)

    painter.drawEllipse(0, 0, diameter - 1, diameter - 1)
    painter.end()

    return QIcon(pix)
