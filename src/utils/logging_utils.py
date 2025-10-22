"""
General logging utilities for real-time log visibility and correlation tracking.

Provides:
- flush_logs() for immediate log output during long-running operations
- Correlation ID tracking via selection_id for tracing requests through the system
- Timing utilities for measuring operation durations
"""

import logging
import logging.handlers
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any
from functools import wraps

# Context variable to store current selection_id across async boundaries
_selection_context: ContextVar[Optional[str]] = ContextVar('selection_id', default=None)

logger = logging.getLogger(__name__)


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


# ============================================================================
# Correlation ID Tracking (for Phase 0 - UI freeze elimination)
# ============================================================================

def generate_selection_id() -> str:
    """
    Generate a unique selection ID for correlation across logs.
    
    Returns:
        A short, unique identifier (8 characters)
    """
    return str(uuid.uuid4())[:8]


def set_selection_context(selection_id: str):
    """Set the current selection ID in context."""
    _selection_context.set(selection_id)


def get_selection_context() -> Optional[str]:
    """Get the current selection ID from context."""
    return _selection_context.get()


def clear_selection_context():
    """Clear the current selection ID from context."""
    _selection_context.set(None)


def log_with_context(level: int, message: str, **kwargs):
    """
    Log a message with selection_id context if available.
    
    Args:
        level: Logging level (e.g., logging.INFO)
        message: Log message
        **kwargs: Additional context to include in log
    """
    selection_id = get_selection_context()
    
    if selection_id:
        # Build context string
        context_parts = [f"selection_id={selection_id}"]
        for key, value in kwargs.items():
            context_parts.append(f"{key}={value}")
        context_str = " ".join(context_parts)
        
        # Log with context
        logger.log(level, f"[{context_str}] {message}")
    else:
        # No context, log normally but include kwargs
        if kwargs:
            context_parts = [f"{key}={value}" for key, value in kwargs.items()]
            context_str = " ".join(context_parts)
            logger.log(level, f"[{context_str}] {message}")
        else:
            logger.log(level, message)


def log_info(message: str, **kwargs):
    """Log INFO message with context."""
    log_with_context(logging.INFO, message, **kwargs)


def log_debug(message: str, **kwargs):
    """Log DEBUG message with context."""
    log_with_context(logging.DEBUG, message, **kwargs)


def log_warning(message: str, **kwargs):
    """Log WARNING message with context."""
    log_with_context(logging.WARNING, message, **kwargs)


def log_error(message: str, **kwargs):
    """Log ERROR message with context."""
    log_with_context(logging.ERROR, message, **kwargs)


class TimingSpan:
    """
    Context manager for timing operations and logging duration.
    
    Usage:
        with TimingSpan("load_vocals"):
            # ... expensive operation ...
            pass
    """
    
    def __init__(self, operation: str, **extra_context):
        """
        Initialize timing span.
        
        Args:
            operation: Name of the operation being timed
            **extra_context: Additional context to include in logs
        """
        self.operation = operation
        self.extra_context = extra_context
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        log_info(f"{self.operation} - started", **self.extra_context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and log duration."""
        self.end_time = time.time()
        duration_ms = (self.end_time - self.start_time) * 1000
        
        if exc_type is not None:
            log_error(
                f"{self.operation} - failed after {duration_ms:.0f}ms",
                error=str(exc_val),
                **self.extra_context
            )
        else:
            log_info(
                f"{self.operation} - completed",
                duration_ms=f"{duration_ms:.0f}",
                **self.extra_context
            )
        
        return False  # Don't suppress exceptions
    
    def get_duration_ms(self) -> Optional[float]:
        """Get duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None


def with_selection_context(func):
    """
    Decorator to automatically set/clear selection context for a function.
    
    The function must have a 'selection_id' parameter or accept **kwargs.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Try to get selection_id from kwargs or args
        selection_id = kwargs.get('selection_id')
        if not selection_id and len(args) > 0 and hasattr(args[0], 'selection_id'):
            selection_id = args[0].selection_id
        
        if selection_id:
            old_context = get_selection_context()
            try:
                set_selection_context(selection_id)
                return func(*args, **kwargs)
            finally:
                if old_context:
                    set_selection_context(old_context)
                else:
                    clear_selection_context()
        else:
            return func(*args, **kwargs)
    
    return wrapper


# Convenience functions for common patterns
def log_selection_start(song_title: str, selection_id: str):
    """Log the start of a song selection."""
    set_selection_context(selection_id)
    log_info(f"Song selection started: {song_title}", song_title=song_title)


def log_selection_complete(song_title: str):
    """Log the completion of a song selection."""
    log_info(f"Song selection completed: {song_title}", song_title=song_title)
    clear_selection_context()


def log_selection_cancelled(song_title: str, reason: str = "User action"):
    """Log the cancellation of a song selection."""
    log_warning(f"Song selection cancelled: {song_title}", reason=reason)
    clear_selection_context()
