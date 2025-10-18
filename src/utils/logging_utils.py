"""
General logging utilities for real-time log visibility.

Provides flush_logs() for immediate log output during long-running operations.
Useful for external tool calls (ffmpeg, ffprobe) and async processing.
"""

import logging
import logging.handlers
import sys
import time


def flush_logs():
    """
    Force immediate flush of all log handlers for real-time visibility.

    Necessary for async logging (QueueHandler) to ensure log messages appear
    immediately during long-running operations like:
    - Model loading (Demucs, PyTorch)
    - Audio processing (ffmpeg, ffprobe)
    - Vocal separation (Spleeter, MDX)
    - Normalization (loudnorm filter)

    Flushes:
        - All active logger handlers (module and root)
        - QueueHandler with small delay for queue processing
        - stdout/stderr streams

    Example:
        >>> logger.info("Starting long operation...")
        >>> flush_logs()  # Ensure message appears immediately
        >>> run_long_operation()
    """
    # Flush all module loggers
    for logger_name in logging.Logger.manager.loggerDict:
        module_logger = logging.getLogger(logger_name)
        for handler in module_logger.handlers:
            handler.flush()

    # Flush root logger handlers (includes async queue handler)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.flush()
        # If it's a QueueHandler, yield to let queue process
        if isinstance(handler, logging.handlers.QueueHandler):
            # 1ms delay to allow queue to drain
            time.sleep(0.001)

    # Force stdout/stderr flush for good measure
    sys.stdout.flush()
    sys.stderr.flush()
