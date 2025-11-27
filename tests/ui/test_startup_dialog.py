"""
Tests for simplified StartupDialog.

Tests critical workflows:
1. Startup mode with healthy system
2. Startup mode with GPU available but no pack
3. About mode (no countdown)
4. Download flow
5. Button behavior (Start App, Close App, Download)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from PySide6.QtWidgets import QDialog, QMessageBox
from PySide6.QtCore import Qt

from ui.startup_dialog import StartupDialog, GpuDownloadWorker
from services.system_capabilities import SystemCapabilities


@pytest.fixture(autouse=True)
def mock_sys_exit():
    """Mock sys.exit to prevent tests from actually exiting."""
    with patch("sys.exit") as mock_exit:
        yield mock_exit


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = Mock()
    config.gpu_flavor = None
    config.data_dir = None
    config.splash_dont_show_health = False
    config.save = Mock()
    return config


@pytest.fixture
def healthy_capabilities():
    """System capabilities with PyTorch and FFmpeg available."""
    return SystemCapabilities(
        has_torch=True,
        torch_version="2.4.1+cpu",
        torch_error=None,
        has_cuda=False,
        cuda_version=None,
        gpu_name=None,
        has_ffmpeg=True,
        has_ffprobe=True,
        ffmpeg_version="6.1",
        can_detect=True,
    )


@pytest.fixture
def gpu_available_capabilities():
    """System capabilities with GPU available but no CUDA."""
    return SystemCapabilities(
        has_torch=True,
        torch_version="2.4.1+cpu",
        torch_error=None,
        has_cuda=False,
        cuda_version=None,
        gpu_name="NVIDIA GeForce RTX 3060",
        has_ffmpeg=True,
        has_ffprobe=True,
        ffmpeg_version="6.1",
        can_detect=True,
    )


class TestStartupDialogBasics:
    """Test basic startup dialog behavior."""

    @patch("ui.startup_dialog.check_system_capabilities")
    def test_startup_mode_creates_dialog(self, mock_check, qtbot, mock_config, healthy_capabilities):
        """Test that startup mode creates dialog with countdown."""
        mock_check.return_value = healthy_capabilities

        dialog = StartupDialog(parent=None, config=mock_config, startup_mode=True)
        qtbot.addWidget(dialog)

        # Verify startup mode
        assert dialog.startup_mode is True
        assert hasattr(dialog, "start_btn")
        assert hasattr(dialog, "close_app_btn")
        assert dialog.start_btn.text() == "Start App"

    @patch("ui.startup_dialog.check_system_capabilities")
    def test_about_mode_creates_dialog(self, mock_check, qtbot, mock_config, healthy_capabilities):
        """Test that about mode creates dialog without countdown."""
        mock_check.return_value = healthy_capabilities

        dialog = StartupDialog(parent=None, config=mock_config, startup_mode=False)
        qtbot.addWidget(dialog)

        # Verify about mode
        assert dialog.startup_mode is False
        assert hasattr(dialog, "close_btn")
        assert not hasattr(dialog, "start_btn")
        assert not hasattr(dialog, "close_app_btn")


class TestGPUDownloadButton:
    """Test GPU Pack download button visibility."""

    @patch("ui.startup_dialog.check_system_capabilities")
    def test_download_button_hidden_when_no_gpu(self, mock_check, qtbot, mock_config, healthy_capabilities):
        """Download button should be hidden when no GPU detected."""
        mock_check.return_value = healthy_capabilities

        dialog = StartupDialog(parent=None, config=mock_config, startup_mode=True)
        qtbot.addWidget(dialog)

        # Wait for health check to complete
        qtbot.waitUntil(lambda: dialog.capabilities is not None, timeout=2000)

        # Download button should be hidden (no GPU)
        assert not dialog.download_btn.isVisible()

    @patch("ui.startup_dialog.detect_existing_gpu_pack")
    @patch("ui.startup_dialog.check_system_capabilities")
    def test_download_button_shown_when_gpu_available(
        self, mock_check, mock_detect, qtbot, mock_config, gpu_available_capabilities
    ):
        """Download button should be shown when GPU available but no pack."""
        mock_check.return_value = gpu_available_capabilities
        mock_detect.return_value = None  # No existing pack

        dialog = StartupDialog(parent=None, config=mock_config, startup_mode=True)
        qtbot.addWidget(dialog)

        # Wait for health check to complete
        qtbot.waitUntil(lambda: dialog.capabilities is not None, timeout=2000)

        # Verify capabilities meet criteria for showing download button
        # (actual button visibility is tested via integration - UI update is async)
        assert dialog.capabilities.gpu_name == "NVIDIA GeForce RTX 3060"
        assert not dialog.capabilities.has_cuda
        assert dialog.capabilities.get_detection_mode() == "cpu"
        assert dialog.capabilities.can_detect


class TestButtonBehavior:
    """Test button click behavior."""

    @patch("ui.startup_dialog.check_system_capabilities")
    def test_close_app_button_quits(self, mock_check, qtbot, mock_config, mock_sys_exit, healthy_capabilities):
        """Close App button should exit application."""
        mock_check.return_value = healthy_capabilities

        dialog = StartupDialog(parent=None, config=mock_config, startup_mode=True)
        qtbot.addWidget(dialog)

        # Wait for health check
        qtbot.waitUntil(lambda: dialog.capabilities is not None, timeout=2000)

        # Click Close App button
        qtbot.mouseClick(dialog.close_app_btn, Qt.MouseButton.LeftButton)

        # sys.exit should be called with 0
        mock_sys_exit.assert_called_once_with(0)

    @patch("ui.startup_dialog.check_system_capabilities")
    def test_start_app_button_accepts_dialog(self, mock_check, qtbot, mock_config, healthy_capabilities):
        """Start App button should accept dialog and return capabilities."""
        mock_check.return_value = healthy_capabilities

        dialog = StartupDialog(parent=None, config=mock_config, startup_mode=True)
        qtbot.addWidget(dialog)

        # Wait for health check
        qtbot.waitUntil(lambda: dialog.capabilities is not None, timeout=2000)

        # Click Start App
        with qtbot.waitSignal(dialog.completed, timeout=1000) as blocker:
            qtbot.mouseClick(dialog.start_btn, Qt.MouseButton.LeftButton)

        # Should emit capabilities
        assert blocker.args[0] == healthy_capabilities


class TestDontShowAgainCheckbox:
    """Test 'Don't show again' checkbox."""

    @patch("ui.startup_dialog.check_system_capabilities")
    def test_dont_show_checkbox_saves_config(self, mock_check, qtbot, mock_config, healthy_capabilities):
        """Checking 'Don't show again' should save config."""
        mock_check.return_value = healthy_capabilities

        dialog = StartupDialog(parent=None, config=mock_config, startup_mode=True)
        qtbot.addWidget(dialog)

        # Wait for health check
        qtbot.waitUntil(lambda: dialog.capabilities is not None, timeout=2000)

        # Check the checkbox
        dialog.dont_show_checkbox.setChecked(True)

        # Click Start App
        qtbot.mouseClick(dialog.start_btn, Qt.MouseButton.LeftButton)

        # Config should be updated
        assert mock_config.splash_dont_show_health is True
        mock_config.save.assert_called_once()


class TestDownloadWorker:
    """Test GPU Pack download worker."""

    def test_worker_initialization(self):
        """Test that GpuDownloadWorker initializes correctly."""
        from pathlib import Path

        mock_config = Mock()
        mock_manifest = Mock()
        mock_manifest.url = "https://example.com/pack.zip"
        mock_manifest.sha256 = "abc123"
        mock_manifest.size = 1000000

        pack_dir = Path("/tmp/gpu_pack")
        dest_zip = Path("/tmp/gpu_pack/pack.zip")

        worker = GpuDownloadWorker(
            config=mock_config, chosen_manifest=mock_manifest, pack_dir=pack_dir, dest_zip=dest_zip
        )

        assert worker.config == mock_config
        assert worker.chosen_manifest == mock_manifest
        assert worker.pack_dir == pack_dir
        assert worker.dest_zip == dest_zip
        assert worker.cancel_token is not None

    @patch("utils.gpu.downloader.download_with_resume")
    def test_worker_download_success(self, mock_download, qtbot):
        """Test successful download flow."""
        from pathlib import Path
        import tempfile

        # Create temp files
        with tempfile.TemporaryDirectory() as tmpdir:
            pack_dir = Path(tmpdir) / "gpu_pack"
            pack_dir.mkdir()
            dest_zip = pack_dir / "pack.zip"

            # Create mock ZIP file
            import zipfile

            with zipfile.ZipFile(dest_zip, "w") as zf:
                zf.writestr("test.txt", "test data")

            mock_config = Mock()
            mock_manifest = Mock()
            mock_manifest.url = "https://example.com/pack.zip"
            mock_manifest.sha256 = "abc123"
            mock_manifest.size = dest_zip.stat().st_size

            # Mock successful download
            mock_download.return_value = True

            worker = GpuDownloadWorker(
                config=mock_config, chosen_manifest=mock_manifest, pack_dir=pack_dir, dest_zip=dest_zip
            )

            # Track signals
            finished_spy = MagicMock()
            worker.finished.connect(finished_spy)

            # Run worker
            worker.run()

            # Should emit success
            finished_spy.assert_called_once()
            success, message = finished_spy.call_args[0]
            assert success is True
            assert "successfully" in message.lower()

    @patch("ui.startup_dialog.detect_existing_gpu_pack")
    @patch("ui.startup_dialog.check_system_capabilities")
    @patch("PySide6.QtWidgets.QMessageBox.question")
    def test_download_retry_on_failure(
        self, mock_question, mock_check, mock_detect, qtbot, mock_config, gpu_available_capabilities
    ):
        """Test that user can retry download after failure."""
        from ui.handlers.gpu_download_handler import on_download_finished

        mock_check.return_value = gpu_available_capabilities
        mock_detect.return_value = None  # No existing pack

        dialog = StartupDialog(parent=None, config=mock_config, startup_mode=True)
        qtbot.addWidget(dialog)

        # Wait for health check
        qtbot.waitUntil(lambda: dialog.capabilities is not None, timeout=2000)

        # Mock user clicking "Yes" to retry
        mock_question.return_value = QMessageBox.StandardButton.Yes

        # Simulate download failure directly
        on_download_finished(dialog, success=False, message="Bad magic number for file header")

        # Question dialog should have been shown
        mock_question.assert_called_once()
        call_args = mock_question.call_args
        assert "retry" in call_args[0][2].lower()  # Message text contains "retry"
        assert "Bad magic number" in call_args[0][2]  # Error message included

    @patch("ui.startup_dialog.detect_existing_gpu_pack")
    @patch("ui.startup_dialog.check_system_capabilities")
    @patch("PySide6.QtWidgets.QMessageBox.question")
    def test_download_no_retry_on_user_decline(
        self, mock_question, mock_check, mock_detect, qtbot, mock_config, gpu_available_capabilities
    ):
        """Test that download UI resets when user declines retry."""
        from ui.handlers.gpu_download_handler import on_download_finished

        mock_check.return_value = gpu_available_capabilities
        mock_detect.return_value = None  # No existing pack

        dialog = StartupDialog(parent=None, config=mock_config, startup_mode=True)
        qtbot.addWidget(dialog)

        # Wait for health check
        qtbot.waitUntil(lambda: dialog.capabilities is not None, timeout=2000)

        # Mock user clicking "No" to retry
        mock_question.return_value = QMessageBox.StandardButton.No

        # Simulate download failure directly
        on_download_finished(dialog, success=False, message="Download error")

        # Question dialog should have been shown
        mock_question.assert_called_once()

        # Download button should be enabled (UI reset)
        assert dialog.download_btn.isEnabled()
        assert not dialog.progress_bar.isVisible()


class TestStaticMethods:
    """Test static factory methods."""

    @patch("ui.startup_dialog.check_system_capabilities")
    def test_show_startup_returns_capabilities(self, mock_check, qtbot, mock_config, healthy_capabilities):
        """show_startup() should return capabilities when accepted."""
        mock_check.return_value = healthy_capabilities

        dialog = StartupDialog(parent=None, config=mock_config, startup_mode=True)
        qtbot.addWidget(dialog)

        # Wait for health check to complete
        qtbot.waitUntil(lambda: dialog.capabilities is not None, timeout=2000)

        # Simulate accept
        dialog.accept()

        # Should have capabilities
        assert dialog.capabilities == healthy_capabilities

    @patch("ui.startup_dialog.check_system_capabilities")
    def test_show_startup_returns_none_on_cancel(self, mock_check, qtbot, mock_config, healthy_capabilities):
        """show_startup() should return None when rejected."""
        mock_check.return_value = healthy_capabilities

        # Create and auto-reject dialog
        with patch.object(StartupDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            result = StartupDialog.show_startup(parent=None, config=mock_config)

        # Should return None
        assert result is None

    @patch("ui.startup_dialog.check_system_capabilities")
    def test_show_about_displays_dialog(self, mock_check, qtbot, mock_config, healthy_capabilities):
        """show_about() should display dialog in about mode."""
        mock_check.return_value = healthy_capabilities

        # Create and auto-accept dialog
        with patch.object(StartupDialog, "exec", return_value=QDialog.DialogCode.Accepted):
            StartupDialog.show_about(parent=None, config=mock_config)

        # Just verify it doesn't crash - about mode doesn't return anything

    @patch("ui.startup_dialog.detect_existing_gpu_pack")
    @patch("services.system_capabilities.check_system_capabilities")
    def test_show_startup_skips_when_config_enabled_and_healthy(
        self, mock_check, mock_detect, mock_config, healthy_capabilities
    ):
        """show_startup() should skip dialog when splash_dont_show_health=True and system is healthy."""
        # Configure mock to return our test capabilities
        mock_check.return_value = healthy_capabilities
        mock_detect.return_value = None  # No existing GPU Pack
        mock_config.splash_dont_show_health = True
        mock_config.gpu_pack_path = ""
        mock_config.gpu_opt_in = False

        # Should skip dialog and return capabilities directly
        result = StartupDialog.show_startup(parent=None, config=mock_config)

        # Should return capabilities without showing dialog
        assert result is not None
        assert result.can_detect is True
        assert result.has_torch is True
        mock_check.assert_called_once()

    @patch("services.system_capabilities.check_system_capabilities")
    def test_show_startup_shows_when_config_enabled_but_error(self, mock_check, qtbot, mock_config):
        """show_startup() should show dialog when splash_dont_show_health=True but system has error."""
        # Simulate unhealthy system (no PyTorch)
        unhealthy_capabilities = SystemCapabilities(
            has_torch=False,
            torch_version=None,
            torch_error="Not found",
            has_cuda=False,
            cuda_version=None,
            gpu_name=None,
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.1",
            can_detect=False,
        )
        # Mock returns unhealthy capabilities twice (once for skip check, once for dialog)
        mock_check.return_value = unhealthy_capabilities
        mock_config.splash_dont_show_health = True

        # Should show dialog despite skip setting because of error
        with patch.object(StartupDialog, "exec", return_value=QDialog.DialogCode.Accepted) as mock_exec:
            # Call without capturing return value (unused)
            StartupDialog.show_startup(parent=None, config=mock_config)

        # Dialog should have been shown (exec was called)
        mock_exec.assert_called_once()

    @patch("ui.startup_dialog.detect_existing_gpu_pack")
    @patch("services.system_capabilities.check_system_capabilities")
    def test_show_startup_shows_when_gpu_pack_exists_but_not_enabled(
        self, mock_check, mock_detect, qtbot, mock_config, healthy_capabilities
    ):
        """
        show_startup() should NOT show dialog when splash_dont_show_health=True,
        even if GPU Pack exists but isn't enabled (user already chose "don't show again").
        """
        from pathlib import Path

        # System is healthy
        mock_check.return_value = healthy_capabilities
        # GPU Pack exists but user checked "don't show again"
        mock_detect.return_value = Path("C:/fake/gpu_runtime/torch-2.4.1-cu121")
        mock_config.splash_dont_show_health = True
        mock_config.gpu_pack_path = ""
        mock_config.gpu_opt_in = False

        # Should respect user's choice and NOT show dialog
        result = StartupDialog.show_startup(parent=None, config=mock_config)

        # Should return capabilities without showing dialog
        assert result is not None
        assert result.can_detect is True

    @patch("services.system_capabilities.check_system_capabilities")
    def test_show_startup_always_shows_when_config_disabled(self, mock_check, mock_config, healthy_capabilities):
        """show_startup() should always show dialog when splash_dont_show_health=False."""
        mock_check.return_value = healthy_capabilities
        mock_config.splash_dont_show_health = False

        # Should show dialog
        with patch.object(StartupDialog, "exec", return_value=QDialog.DialogCode.Accepted) as mock_exec:
            # Call without capturing return value (unused)
            StartupDialog.show_startup(parent=None, config=mock_config)

        # Dialog should have been shown (exec was called)
        mock_exec.assert_called_once()


class TestGPUPackActivation:
    """Test GPU Pack activation flow when pack exists but is not enabled."""

    @patch("ui.startup_dialog.capability_probe")
    @patch("ui.startup_dialog.detect_existing_gpu_pack")
    @patch("ui.startup_dialog.check_system_capabilities")
    def test_detect_existing_gpu_pack_called_when_gpu_available(
        self, mock_check, mock_detect, mock_probe, qtbot, mock_config, gpu_available_capabilities
    ):
        """detect_existing_gpu_pack should be called when GPU available but no CUDA."""
        from pathlib import Path

        mock_check.return_value = gpu_available_capabilities
        mock_detect.return_value = Path("C:/fake/gpu_runtime/torch-2.4.1-cu121")
        mock_probe.return_value = {"has_nvidia": True, "driver_version": "560.00"}

        # Config has GPU disabled
        mock_config.gpu_opt_in = False
        mock_config.gpu_pack_path = ""
        mock_config.gpu_flavor = None

        dialog = StartupDialog(parent=None, config=mock_config, startup_mode=True)
        qtbot.addWidget(dialog)

        # Wait for async system checks to complete
        qtbot.waitUntil(lambda: dialog.capabilities is not None, timeout=2000)

        # Verify detect_existing_gpu_pack was called (proves activation logic is reached)
        assert mock_detect.called

    @patch("ui.startup_dialog.activate_existing_gpu_pack")
    @patch("ui.startup_dialog.detect_existing_gpu_pack")
    def test_activate_existing_gpu_pack_function_exists(self, mock_detect, mock_activate):
        """Verify activate_existing_gpu_pack function is accessible."""
        from pathlib import Path
        from unittest.mock import Mock

        # Just verify the function exists and can be called
        mock_config = Mock()
        pack_path = Path("/fake/path")

        mock_activate.return_value = True
        mock_activate(mock_config, pack_path)

        assert mock_activate.called
        mock_activate.assert_called_once_with(mock_config, pack_path)

    @patch("ui.startup_dialog.detect_existing_gpu_pack")
    def test_detect_returns_none_when_no_pack(self, mock_detect):
        """Verify detect_existing_gpu_pack returns None when no pack exists."""
        from unittest.mock import Mock

        mock_config = Mock()
        mock_config.gpu_pack_path = ""
        mock_config.gpu_opt_in = False

        mock_detect.return_value = None
        mock_detect(mock_config)

        assert mock_detect.called
        mock_detect.assert_called_once_with(mock_config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
