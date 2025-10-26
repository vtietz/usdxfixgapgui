"""
Retry Policy with exponential backoff orchestration.

Provides configurable retry logic with exponential backoff,
max retries, and callback support.
"""

import logging
import time
from typing import TypeVar, Callable, Optional

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryPolicy:
    """Exponential backoff retry orchestration."""

    def __init__(
        self,
        max_retries: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0
    ):
        """
        Initialize retry policy.

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            backoff_factor: Delay multiplier for each retry
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def execute(
        self,
        operation: Callable[[], T],
        on_retry: Optional[Callable[[int, Exception], None]] = None
    ) -> T:
        """
        Execute operation with retry logic.

        Args:
            operation: Function to execute
            on_retry: Optional callback(attempt, exception) called on retry

        Returns:
            Result of operation

        Raises:
            Last exception if all retries exhausted
        """
        delay = self.initial_delay
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return operation()
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )

                if on_retry:
                    on_retry(attempt, e)

                if attempt < self.max_retries - 1:
                    time.sleep(delay)
                    delay = min(delay * self.backoff_factor, self.max_delay)

        # All retries exhausted - this should never happen if max_retries > 0
        if last_exception:
            raise last_exception
        raise RuntimeError("Operation failed with no exception recorded")