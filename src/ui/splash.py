"""Application splash screen helpers."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor, QLinearGradient
from PySide6.QtCore import Qt

from common.constants import APP_NAME, APP_DESCRIPTION
from utils.files import resource_path
from utils.version import get_version

logger = logging.getLogger(__name__)


def create_splash_screen(app: QApplication, duration_ms: int = 5000) -> Optional[Tuple[QSplashScreen, int]]:
    """Create and display the splash screen, returning (splash, duration)."""
    try:
        version = get_version()
        pixmap = _build_splash_pixmap(version)
        splash = QSplashScreen(pixmap)
        splash.setWindowFlag(Qt.WindowStaysOnTopHint)
        splash.show()
        app.processEvents()
        return splash, duration_ms
    except Exception:
        logger.exception("Failed to initialize splash screen")
        return None


def _build_splash_pixmap(version: str) -> QPixmap:
    """Render splash pixmap with logo and version text."""
    width, height = 500, 320
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)

    gradient = QLinearGradient(0, 0, 0, height)
    gradient.setColorAt(0.0, QColor(32, 32, 34))
    gradient.setColorAt(1.0, QColor(20, 20, 22))
    painter.fillRect(pixmap.rect(), gradient)

    logo = _load_logo()
    max_logo = 170
    if logo.width() > max_logo or logo.height() > max_logo:
        logo = logo.scaled(
            max_logo,
            max_logo,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    logo_x = (width - logo.width()) // 2
    logo_y = 40
    painter.drawPixmap(logo_x, logo_y, logo)

    painter.setPen(QColor(240, 240, 240))
    title_font = QFont("Segoe UI", 26, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.drawText(
        0,
        logo_y + logo.height() + 18,
        width,
        40,
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        APP_NAME,
    )

    painter.setPen(QColor(180, 180, 180))
    subtitle_font = QFont("Segoe UI", 12)
    painter.setFont(subtitle_font)
    painter.drawText(
        0,
        logo_y + logo.height() + 52,
        width,
        30,
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        APP_DESCRIPTION,
    )

    version_font = QFont("Segoe UI", 8)
    painter.setFont(version_font)
    painter.setPen(QColor(150, 150, 150))
    painter.drawText(
        -3,
        height - 15,
        width,
        10,
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        f"{version}",
    )

    painter.end()
    return pixmap


def _load_logo() -> QPixmap:
    """Load the highest fidelity logo available."""
    for candidate in ("assets/usdxfixgap-icon.png", "assets/usdxfixgap-icon.ico"):
        pixmap = QPixmap(resource_path(candidate))
        if not pixmap.isNull():
            return pixmap

    fallback = QPixmap(180, 180)
    fallback.fill(QColor(30, 30, 30))
    return fallback
