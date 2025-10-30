"""
Tests for startup splash screen integration.
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog

from ui.splash_screen import StartupSplash
from services.system_capabilities import SystemCapabilities


@pytest.fixture
def mock_config():
    """Mock config object."""
    config = MagicMock()
    config.gpu_opt_in = False
    return config


class TestStartupSplash:
    """Tests for StartupSplash dialog."""

    def test_splash_initializes_without_error(self, qtbot, mock_config):
        """Splash screen should initialize UI without error."""
        splash = StartupSplash(config=mock_config)
        qtbot.addWidget(splash)

        # Check UI elements exist
        assert splash.status_label is not None
        assert splash.progress is not None
        assert splash.log_text is not None
        assert splash.button_container is not None

    def test_splash_logs_messages(self, qtbot, mock_config):
        """Splash should append messages to log output."""
        splash = StartupSplash(config=mock_config)
        qtbot.addWidget(splash)

        splash.log("Test message 1")
        splash.log("Test message 2")

        log_content = splash.log_text.toPlainText()
        assert "Test message 1" in log_content
        assert "Test message 2" in log_content

    @patch('ui.splash_screen.check_system_capabilities')
    def test_run_method_starts_checks(self, mock_check, qtbot, mock_config):
        """run() should start capability checks."""
        # Mock successful capabilities
        mock_caps = SystemCapabilities(
            has_torch=True,
            torch_version="2.5.1",
            torch_error=None,
            has_cuda=False,
            cuda_version=None,
            gpu_name=None,
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=True
        )
        mock_check.return_value = mock_caps

        splash = StartupSplash(config=mock_config)
        qtbot.addWidget(splash)

        # Mock exec() to prevent dialog from showing and trigger checks manually
        with patch.object(splash, 'exec', return_value=QDialog.DialogCode.Accepted):
            # Manually call _run_checks since exec is mocked
            splash._run_checks()
            # Wait for any async operations
            qtbot.wait(200)
            # Run splash (should return capabilities)
            result = splash.run()

        # Should have called check_system_capabilities
        mock_check.assert_called_once()

        # Should return capabilities
        assert result is not None
        assert result.has_torch is True
        assert result.can_detect is True

    @patch('ui.splash_screen.check_system_capabilities')
    def test_splash_shows_gpu_prompt_when_needed(self, mock_check, qtbot, mock_config):
        """Splash should show GPU Pack prompt if gpu_opt_in enabled but no CUDA."""
        # GPU enabled but no CUDA
        mock_config.gpu_opt_in = True
        mock_caps = SystemCapabilities(
            has_torch=True,
            torch_version="2.5.1",
            torch_error=None,
            has_cuda=False,
            cuda_version=None,
            gpu_name=None,
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=True
        )
        mock_check.return_value = mock_caps

        splash = StartupSplash(config=mock_config)
        qtbot.addWidget(splash)

        # Spy on _show_gpu_pack_prompt method
        with patch.object(splash, '_show_gpu_pack_prompt') as mock_show_gpu:
            # Run checks
            splash._run_checks()
            # Wait for UI to update
            qtbot.wait(200)

            # Should have called _show_gpu_pack_prompt
            mock_show_gpu.assert_called_once()

    @patch('ui.splash_screen.check_system_capabilities')
    def test_splash_auto_closes_when_ready(self, mock_check, qtbot, mock_config):
        """Splash should auto-close when system is ready."""
        # All capabilities available, no GPU needed
        mock_caps = SystemCapabilities(
            has_torch=True,
            torch_version="2.5.1",
            torch_error=None,
            has_cuda=False,
            cuda_version=None,
            gpu_name=None,
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=True
        )
        mock_check.return_value = mock_caps

        splash = StartupSplash(config=mock_config)
        qtbot.addWidget(splash)

        # Track dialog state
        closed = False
        def on_finished():
            nonlocal closed
            closed = True
        splash.finished.connect(on_finished)

        # Run checks
        splash._run_checks()

        # Wait for auto-close (1000ms + buffer)
        qtbot.wait(1500)

        # Should have closed
        assert closed is True

    @patch('ui.splash_screen.check_system_capabilities')
    def test_splash_emits_gpu_pack_requested_signal(self, mock_check, qtbot, mock_config):
        """GPU Pack button should emit gpu_pack_requested signal."""
        mock_config.gpu_opt_in = True
        mock_caps = SystemCapabilities(
            has_torch=True,
            torch_version="2.5.1",
            torch_error=None,
            has_cuda=False,
            cuda_version=None,
            gpu_name=None,
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=True
        )
        mock_check.return_value = mock_caps

        splash = StartupSplash(config=mock_config)
        qtbot.addWidget(splash)

        # Run checks to show GPU buttons
        splash._run_checks()
        qtbot.wait(100)

        # Connect signal spy
        signal_emitted = False
        def on_gpu_requested():
            nonlocal signal_emitted
            signal_emitted = True
        splash.gpu_pack_requested.connect(on_gpu_requested)

        # Click GPU Pack button
        qtbot.mouseClick(splash.gpu_pack_btn, Qt.MouseButton.LeftButton)

        # Should emit signal
        assert signal_emitted is True

    @patch('ui.splash_screen.check_system_capabilities')
    def test_use_cpu_button_disables_gpu_opt_in(self, mock_check, qtbot, mock_config):
        """Use CPU button should disable gpu_opt_in in config after confirming."""
        mock_config.gpu_opt_in = True
        mock_caps = SystemCapabilities(
            has_torch=True,
            torch_version="2.5.1",
            torch_error=None,
            has_cuda=False,
            cuda_version=None,
            gpu_name=None,
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=True
        )
        mock_check.return_value = mock_caps

        splash = StartupSplash(config=mock_config)
        qtbot.addWidget(splash)

        # Run checks to show GPU buttons
        splash._run_checks()
        qtbot.wait(100)

        # First click: Show GPU Pack offer
        qtbot.mouseClick(splash.use_cpu_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(50)

        # Button should now say "No, Use CPU Mode"
        assert splash.use_cpu_btn.text() == "No, Use CPU Mode"

        # Second click: Confirm CPU mode (this triggers finish)
        with qtbot.waitSignal(splash.finished, timeout=2000):
            qtbot.mouseClick(splash.use_cpu_btn, Qt.MouseButton.LeftButton)

        # Should have disabled GPU opt-in
        assert mock_config.gpu_opt_in is False
        mock_config.save.assert_called_once()

    @patch('ui.splash_screen.check_system_capabilities')
    def test_splash_shows_error_when_torch_missing(self, mock_check, qtbot, mock_config):
        """Splash should show error message when PyTorch missing."""
        mock_caps = SystemCapabilities(
            has_torch=False,
            torch_version=None,
            torch_error="PyTorch not installed",
            has_cuda=False,
            cuda_version=None,
            gpu_name=None,
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=False
        )
        mock_check.return_value = mock_caps

        splash = StartupSplash(config=mock_config)
        qtbot.addWidget(splash)

        # Spy on _show_continue_button method
        with patch.object(splash, '_show_continue_button') as mock_show_continue:
            # Run checks
            splash._run_checks()
            # Wait for UI to update
            qtbot.wait(200)

            # Should show error in log
            log_content = splash.log_text.toPlainText()
            assert "PyTorch not available" in log_content or "❌" in log_content

            # Should have called _show_continue_button
            mock_show_continue.assert_called_once()
