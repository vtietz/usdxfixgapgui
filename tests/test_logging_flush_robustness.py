"""
Test logging flush robustness against None handlers and broken handlers.

Regression test for bug where flush_logs() would crash with:
    AttributeError: 'NoneType' object has no attribute 'flush'
"""

import logging
import pytest
from unittest.mock import Mock, MagicMock
from utils.logging_utils import flush_logs


class TestFlushLogsRobustness:
    """Test flush_logs() handles edge cases gracefully."""

    def test_flush_logs_with_none_handler(self):
        """Test that flush_logs() doesn't crash when handler is None."""
        # Setup: Create a logger with a None handler
        test_logger = logging.getLogger("test_none_handler")
        test_logger.handlers = [None]  # Simulate broken state

        # This should not raise AttributeError
        flush_logs()

        # Cleanup
        test_logger.handlers = []

    def test_flush_logs_with_broken_handler(self):
        """Test that flush_logs() doesn't crash when handler.flush() raises."""
        # Setup: Create a mock handler that raises on flush()
        broken_handler = Mock()
        broken_handler.flush.side_effect = Exception("Handler is broken")

        test_logger = logging.getLogger("test_broken_handler")
        test_logger.handlers = [broken_handler]

        # This should not raise Exception (it should be caught and ignored)
        flush_logs()

        # Verify flush was attempted
        assert broken_handler.flush.called

        # Cleanup
        test_logger.handlers = []

    def test_flush_logs_with_mixed_handlers(self):
        """Test flush_logs() with mix of None, broken, and good handlers."""
        # Setup: Mix of different handler states
        good_handler = Mock()
        good_handler.flush = MagicMock()

        broken_handler = Mock()
        broken_handler.flush.side_effect = OSError("Handler closed")

        test_logger = logging.getLogger("test_mixed_handlers")
        test_logger.handlers = [
            None,  # None handler
            good_handler,  # Working handler
            broken_handler,  # Broken handler
            None,  # Another None
        ]

        # This should not crash despite None and broken handlers
        flush_logs()

        # Verify good handler was flushed
        assert good_handler.flush.called

        # Cleanup
        test_logger.handlers = []

    def test_flush_logs_normal_operation(self):
        """Test that flush_logs() works normally with proper handlers."""
        # Setup: Create proper handlers
        handler1 = Mock()
        handler1.flush = MagicMock()

        handler2 = Mock()
        handler2.flush = MagicMock()

        test_logger = logging.getLogger("test_normal_handlers")
        test_logger.handlers = [handler1, handler2]

        # Should work without issues
        flush_logs()

        # Verify both handlers were flushed
        assert handler1.flush.called
        assert handler2.flush.called

        # Cleanup
        test_logger.handlers = []
