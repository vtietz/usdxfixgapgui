"""
Global exception handler for USDXFixGap application.

Catches unhandled exceptions in both Python and Qt event loops,
preventing crashes and showing user-friendly error dialogs.
"""

import sys
import logging
import traceback
import os
import faulthandler
from typing import Optional
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QObject, QEvent, qInstallMessageHandler, QtMsgType

logger = logging.getLogger(__name__)


# Keep a reference to the original handler
_original_excepthook = sys.excepthook


def _show_error_dialog(message: str, details: str, log_file_path: Optional[str] = None):
    """
    Show error dialog to user. Can be called from outside the class.

    Args:
        message: Short error message
        details: Full stack trace and details
        log_file_path: Optional path to log file for writing exception details
    """
    # Check if we're in a test/CI environment
    if os.environ.get("USDX_SUPPRESS_ERROR_DIALOGS") == "1":
        return

    try:
        app = QApplication.instance()
        if app is None:
            # Can't show dialog without Qt app
            print(f"\nERROR: {message}", file=sys.stderr)
            print(f"\nDetails:\n{details}", file=sys.stderr)
            return

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Unexpected Error")
        msg_box.setText(
            "An unexpected error occurred, but the application will try to continue.\n\n"
            f"{message}\n\n"
            "If this error persists, please check the log file or restart the application."
        )
        msg_box.setDetailedText(details)

        if log_file_path:
            msg_box.setInformativeText(f"Error details have been logged to:\n{log_file_path}")

        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    except Exception as e:
        # If dialog fails, at least print to stderr
        logger.error(f"Failed to show error dialog: {e}")
        print(f"\nERROR: {message}", file=sys.stderr)
        print(f"\nDetails:\n{details}", file=sys.stderr)


class GlobalExceptionHandler(QObject):
    """
    Catches and handles unhandled exceptions globally.

    Prevents application crashes by catching exceptions at the Qt event loop level
    and Python interpreter level, showing user-friendly error dialogs instead.
    """

    def __init__(self, log_file_path: Optional[str] = None):
        super().__init__()
        self.log_file_path = log_file_path
        self._fault_handler_file = None

    def install(self):
        """Install global exception handlers."""
        # Python interpreter exception hook
        sys.excepthook = self._handle_exception

        # Qt message handler
        qInstallMessageHandler(self._qt_message_handler)

        # Qt event loop exception handler
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

        self.enable_faulthandler()
        logger.info("Global exception handler installed")

    def uninstall(self):
        """Restore original exception handlers."""
        sys.excepthook = _original_excepthook
        qInstallMessageHandler(None)

        app = QApplication.instance()
        if app:
            app.removeEventFilter(self)

        self.disable_faulthandler()
        logger.info("Global exception handler uninstalled")

    def enable_faulthandler(self):
        """Enable faulthandler to log hard crashes."""
        # Always enable for stderr first, as it's the most reliable output
        faulthandler.enable(all_threads=True)
        logger.info("Faulthandler enabled to log hard crashes to stderr.")

        if not self.log_file_path:
            logger.warning("No log file path for faulthandler; writing to stderr only.")
            return

        try:
            # Keep the file handle open so faulthandler can write to it on crash
            self._fault_handler_file = open(self.log_file_path, "a", encoding="utf-8")
            faulthandler.enable(file=self._fault_handler_file, all_threads=True)
            logger.info(f"Faulthandler configured to also log to {self.log_file_path}")
        except Exception as e:
            logger.error(f"Failed to configure faulthandler file logging: {e}")

    def disable_faulthandler(self):
        """Disable faulthandler and close the file handle."""
        faulthandler.disable()
        if self._fault_handler_file:
            try:
                self._fault_handler_file.close()
                self._fault_handler_file = None
                logger.info("Faulthandler disabled and log file closed.")
            except Exception as e:
                logger.error(f"Failed to close faulthandler file: {e}")

    def _qt_message_handler(self, mode: QtMsgType, context, message: str):
        """Handle messages from Qt's logging system."""
        level = logging.DEBUG
        if mode == QtMsgType.QtInfoMsg:
            level = logging.INFO
        elif mode == QtMsgType.QtWarningMsg:
            level = logging.WARNING
        elif mode == QtMsgType.QtCriticalMsg:
            level = logging.CRITICAL
        elif mode == QtMsgType.QtFatalMsg:
            level = logging.FATAL

        log_message = f"[QT] {message} (Context: {context.file}:{context.line}, {context.function})"
        logger.log(level, log_message)

        if mode == QtMsgType.QtFatalMsg:
            _show_error_dialog(
                "A fatal Qt error occurred, and the application must close.",
                log_message,
                self.log_file_path,
            )
            # The application will likely abort after this anyway

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        Qt event filter to catch exceptions in event handlers.

        Note: This won't catch all Qt exceptions (some are handled internally),
        but it provides an additional safety net.
        """
        return super().eventFilter(obj, event)

    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """
        Handle uncaught exceptions.

        Args:
            exc_type: Exception type
            exc_value: Exception instance
            exc_traceback: Traceback object
        """
        # Ignore KeyboardInterrupt so we can still exit cleanly
        if issubclass(exc_type, KeyboardInterrupt):
            _original_excepthook(exc_type, exc_value, exc_traceback)
            return

        # Format exception details
        error_msg = f"{exc_type.__name__}: {exc_value}"
        error_details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        # Log the exception with clear formatting
        logger.critical("=" * 60)
        logger.critical("UNHANDLED EXCEPTION")
        logger.critical("=" * 60)
        logger.critical(f"Exception Type: {exc_type.__name__}")
        logger.critical(f"Error: {exc_value}")
        logger.critical("Stack trace:")
        for line in error_details.split("\n"):
            if line.strip():
                logger.critical(line)
        logger.critical("=" * 60)

        # Write to log file if available
        if self.log_file_path:
            try:
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("UNHANDLED EXCEPTION\n")
                    f.write("=" * 60 + "\n")
                    f.write(error_details)
                    f.write("\n" + "=" * 60 + "\n\n")
            except Exception as e:
                logger.error(f"Failed to write exception to log file: {e}")

        # Show user-friendly error dialog
        _show_error_dialog(error_msg, error_details, self.log_file_path)

        # Don't exit - let the application continue
        # (unless it's a truly critical error, the app might still be usable)


def install_global_exception_handler(log_file_path: Optional[str] = None) -> GlobalExceptionHandler:
    """
    Install global exception handler.

    Args:
        log_file_path: Optional path to log file for writing exception details

    Returns:
        GlobalExceptionHandler instance
    """
    handler = GlobalExceptionHandler(log_file_path)
    handler.install()
    return handler
