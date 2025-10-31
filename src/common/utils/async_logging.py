import logging
import logging.handlers
import queue
import atexit
from typing import Optional

# Global reference to prevent garbage collection
_queue_listener = None
_shutdown_registered = False

def setup_async_logging(log_level=logging.INFO, log_file_path: Optional[str] = None,
                       max_bytes: int = 10*1024*1024, backup_count: int = 3) -> None:
    """
    Set up asynchronous logging to prevent logging operations from blocking the main thread.

    Args:
        log_level: The logging level (e.g., logging.INFO)
        log_file_path: Path to the log file, if None, only console logging is set up
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup files to keep
    """
    global _queue_listener, _shutdown_registered

    # Create the queue and queue handler
    log_queue = queue.Queue(-1)  # No limit on queue size
    queue_handler = logging.handlers.QueueHandler(log_queue)

    # Configure the root logger with the queue handler
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers to avoid duplicate logs
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Add the queue handler to the root logger
    root_logger.addHandler(queue_handler)

    # Create the actual handlers that will process the log records
    handlers = []

    # Create and add file handler if a log file path is provided
    if log_file_path:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s',
                                          datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    # Create and start the queue listener with the handlers
    _queue_listener = logging.handlers.QueueListener(log_queue, *handlers, respect_handler_level=True)
    _queue_listener.start()

    # Register atexit hook (one-time) to ensure cleanup on unexpected exit
    if not _shutdown_registered:
        atexit.register(shutdown_async_logging)
        _shutdown_registered = True

    logging.info("Asynchronous logging setup completed")

def shutdown_async_logging():
    """Stop the queue listener thread and wait for it to finish (idempotent)."""
    global _queue_listener
    
    if _queue_listener is None:
        # Already shut down or never started
        return
    
    # Stop the listener (signals thread to stop)
    _queue_listener.stop()
    
    # Wait for the listener thread to actually stop (with timeout)
    if hasattr(_queue_listener, '_thread') and _queue_listener._thread:
        _queue_listener._thread.join(timeout=2.0)
        if _queue_listener._thread.is_alive():
            logging.warning("Logging thread did not stop within timeout")
    
    _queue_listener = None
    
    # Flush and close all handlers
    logging.shutdown()