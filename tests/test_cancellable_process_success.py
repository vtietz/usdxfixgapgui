"""Unit tests for run_cancellable_process success path."""

import sys
import pytest

from utils.cancellable_process import run_cancellable_process


class TestCancellableProcessSuccess:
    """Unit tests for successful subprocess execution"""

    def test_aggregates_stdout_and_stderr(self):
        """Test: Successfully aggregates stdout and stderr from subprocess"""
        # Setup: Command that writes to both stdout and stderr
        # Using sys.executable ensures the executable exists on the system
        command = [
            sys.executable,
            "-c",
            "import sys; print('output line'); sys.stderr.write('error line\\n')"
        ]

        # Action: Run the command
        returncode, stdout, stderr = run_cancellable_process(command)

        # Assert: Successful execution
        assert returncode == 0, f"Expected returncode 0, got {returncode}"

        # Assert: Stdout captured
        assert "output line" in stdout, f"Expected 'output line' in stdout, got: {stdout}"

        # Assert: Stderr captured
        assert "error line" in stderr, f"Expected 'error line' in stderr, got: {stderr}"

    def test_handles_empty_output(self):
        """Test: Handles command with no output"""
        command = [
            sys.executable,
            "-c",
            "pass"  # Does nothing
        ]

        # Action
        returncode, stdout, stderr = run_cancellable_process(command)

        # Assert: Successful with empty output
        assert returncode == 0
        assert stdout == "" or stdout.isspace()  # May be empty or just whitespace
        assert stderr == "" or stderr.isspace()

    def test_handles_multi_line_output(self):
        """Test: Correctly captures multi-line output"""
        command = [
            sys.executable,
            "-c",
            "for i in range(3): print(f'line {i}')"
        ]

        # Action
        returncode, stdout, stderr = run_cancellable_process(command)

        # Assert
        assert returncode == 0
        assert "line 0" in stdout
        assert "line 1" in stdout
        assert "line 2" in stdout

    def test_non_zero_returncode(self):
        """Test: Captures non-zero return code from failing command"""
        command = [
            sys.executable,
            "-c",
            "import sys; sys.exit(42)"
        ]

        # Action
        returncode, stdout, stderr = run_cancellable_process(command)

        # Assert: Non-zero returncode captured
        assert returncode == 42

    def test_check_cancellation_callback(self):
        """Test: check_cancellation callback is respected"""
        # Setup: Callback that cancels immediately
        cancelled = False

        def cancel_check():
            nonlocal cancelled
            cancelled = True
            return True  # Signal cancellation

        command = [
            sys.executable,
            "-c",
            "import time; time.sleep(10)"  # Long-running command
        ]

        # Action: Run with cancellation callback
        # Note: The implementation raises Exception when cancelled
        with pytest.raises(Exception, match="Process cancelled"):
            returncode, stdout, stderr = run_cancellable_process(command, check_cancellation=cancel_check)

        # Assert: Cancellation was checked
        assert cancelled, "Cancellation callback should have been called"