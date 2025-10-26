"""
Tests for GPU Pack download dialog display logic.

Verifies that the GPU Pack download dialog is shown/hidden based on:
- GPU hardware presence
- GPU Pack installation status
- GPU bootstrap success/failure
- System PyTorch with CUDA detection
- User preference settings
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path


class TestGpuDialogLogic:
    """Test cases for GPU Pack dialog display logic."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config with default settings."""
        config = Mock()
        config.gpu_pack_dialog_dont_show = False
        config.prefer_system_pytorch = True
        config.data_dir = str(Path.home() / ".local" / "share" / "USDXFixGap")
        return config

    @pytest.fixture
    def mock_capability_nvidia(self):
        """Mock capability probe returning NVIDIA GPU detected."""
        return {
            'has_nvidia': True,
            'gpu_names': ['NVIDIA GeForce RTX 3060'],
            'driver_version': '576.80'
        }

    @pytest.fixture
    def mock_capability_no_nvidia(self):
        """Mock capability probe returning no NVIDIA GPU."""
        return {
            'has_nvidia': False,
            'gpu_names': [],
            'driver_version': None
        }

    @patch('utils.gpu_pack_cleaner.should_clean_on_startup')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.capability_probe')
    @patch('utils.gpu_startup_logger.is_gpu_pack_installed')
    @patch('ui.gpu_download_dialog.GpuPackDownloadDialog')
    def test_dialog_shown_when_nvidia_gpu_no_pack_no_system_cuda(
        self,
        mock_dialog_class,
        mock_is_installed,
        mock_capability_probe,
        mock_detect_system,
        mock_auto_recover,
        mock_should_clean,
        mock_config,
        mock_capability_nvidia
    ):
        """Dialog SHOULD appear: NVIDIA GPU, no GPU Pack, no system CUDA, GPU disabled."""
        from utils.gpu_startup_logger import show_gpu_pack_dialog_if_needed

        # Setup mocks
        mock_capability_probe.return_value = mock_capability_nvidia
        mock_detect_system.return_value = None
        mock_auto_recover.return_value = None
        mock_is_installed.return_value = False
        mock_should_clean.return_value = False

        mock_dialog_instance = Mock()
        mock_dialog_class.return_value = mock_dialog_instance

        gpu_enabled = False

        # Call function
        result = show_gpu_pack_dialog_if_needed(mock_config, gpu_enabled)

        # Verify dialog was shown
        assert result is not None, "Dialog should have been shown"
        mock_dialog_class.assert_called_once_with(mock_config)
        mock_dialog_instance.show.assert_called_once()

    @patch('utils.gpu_pack_cleaner.should_clean_on_startup')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.capability_probe')
    @patch('utils.gpu_startup_logger.is_gpu_pack_installed')
    @patch('ui.gpu_download_dialog.GpuPackDownloadDialog')
    def test_dialog_not_shown_when_gpu_enabled(
        self,
        mock_dialog_class,
        mock_is_installed,
        mock_capability_probe,
        mock_detect_system,
        mock_auto_recover,
        mock_should_clean,
        mock_config,
        mock_capability_nvidia
    ):
        """Dialog should NOT appear: GPU is already enabled."""
        from utils.gpu_startup_logger import show_gpu_pack_dialog_if_needed

        # Setup mocks
        mock_capability_probe.return_value = mock_capability_nvidia
        mock_detect_system.return_value = None
        mock_auto_recover.return_value = None
        mock_is_installed.return_value = False
        mock_should_clean.return_value = False

        gpu_enabled = True  # GPU already working

        # Call function
        result = show_gpu_pack_dialog_if_needed(mock_config, gpu_enabled)

        # Verify dialog was NOT shown
        assert result is None, "Dialog should NOT have been shown when GPU is enabled"
        mock_dialog_class.assert_not_called()

    @patch('utils.gpu_pack_cleaner.should_clean_on_startup')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.capability_probe')
    @patch('utils.gpu_startup_logger.is_gpu_pack_installed')
    @patch('ui.gpu_download_dialog.GpuPackDownloadDialog')
    def test_dialog_not_shown_when_no_nvidia_gpu(
        self,
        mock_dialog_class,
        mock_is_installed,
        mock_capability_probe,
        mock_detect_system,
        mock_auto_recover,
        mock_should_clean,
        mock_config,
        mock_capability_no_nvidia
    ):
        """Dialog should NOT appear: No NVIDIA GPU detected."""
        from utils.gpu_startup_logger import show_gpu_pack_dialog_if_needed

        # Setup mocks
        mock_capability_probe.return_value = mock_capability_no_nvidia
        mock_detect_system.return_value = None
        mock_auto_recover.return_value = None
        mock_is_installed.return_value = False
        mock_should_clean.return_value = False

        gpu_enabled = False

        # Call function
        result = show_gpu_pack_dialog_if_needed(mock_config, gpu_enabled)

        # Verify dialog was NOT shown
        assert result is None, "Dialog should NOT have been shown without NVIDIA GPU"
        mock_dialog_class.assert_not_called()

    @patch('utils.gpu_pack_cleaner.should_clean_on_startup')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.capability_probe')
    @patch('utils.gpu_startup_logger.is_gpu_pack_installed')
    @patch('ui.gpu_download_dialog.GpuPackDownloadDialog')
    def test_dialog_not_shown_when_gpu_pack_already_installed(
        self,
        mock_dialog_class,
        mock_is_installed,
        mock_capability_probe,
        mock_detect_system,
        mock_auto_recover,
        mock_should_clean,
        mock_config,
        mock_capability_nvidia
    ):
        """Dialog should NOT appear: GPU Pack already installed."""
        from utils.gpu_startup_logger import show_gpu_pack_dialog_if_needed

        # Setup mocks
        mock_capability_probe.return_value = mock_capability_nvidia
        mock_detect_system.return_value = None
        mock_auto_recover.return_value = None
        mock_is_installed.return_value = True  # GPU Pack installed
        mock_should_clean.return_value = False

        gpu_enabled = False

        # Call function
        result = show_gpu_pack_dialog_if_needed(mock_config, gpu_enabled)

        # Verify dialog was NOT shown
        assert result is None, "Dialog should NOT have been shown when GPU Pack is installed"
        mock_dialog_class.assert_not_called()

    @patch('utils.gpu_pack_cleaner.should_clean_on_startup')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.capability_probe')
    @patch('utils.gpu_startup_logger.is_gpu_pack_installed')
    @patch('ui.gpu_download_dialog.GpuPackDownloadDialog')
    def test_dialog_not_shown_when_system_pytorch_cuda_detected(
        self,
        mock_dialog_class,
        mock_is_installed,
        mock_capability_probe,
        mock_detect_system,
        mock_auto_recover,
        mock_should_clean,
        mock_config,
        mock_capability_nvidia
    ):
        """Dialog should NOT appear: System PyTorch with CUDA detected."""
        from utils.gpu_startup_logger import show_gpu_pack_dialog_if_needed

        # Setup mocks
        mock_capability_probe.return_value = mock_capability_nvidia
        mock_detect_system.return_value = {
            'torch_version': '2.0.0',
            'cuda_version': '12.1'
        }
        mock_auto_recover.return_value = None
        mock_is_installed.return_value = False
        mock_should_clean.return_value = False

        gpu_enabled = False

        # Call function
        result = show_gpu_pack_dialog_if_needed(mock_config, gpu_enabled)

        # Verify dialog was NOT shown (system CUDA makes GPU Pack unnecessary)
        assert result is None, "Dialog should NOT have been shown when system CUDA is available"
        mock_dialog_class.assert_not_called()

    @patch('utils.gpu_pack_cleaner.should_clean_on_startup')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.capability_probe')
    @patch('utils.gpu_startup_logger.is_gpu_pack_installed')
    @patch('ui.gpu_download_dialog.GpuPackDownloadDialog')
    def test_dialog_not_shown_when_user_suppressed(
        self,
        mock_dialog_class,
        mock_is_installed,
        mock_capability_probe,
        mock_detect_system,
        mock_auto_recover,
        mock_should_clean,
        mock_config,
        mock_capability_nvidia
    ):
        """Dialog should NOT appear: User set GpuPackDialogDontShow=true."""
        from utils.gpu_startup_logger import show_gpu_pack_dialog_if_needed

        # Setup mocks
        mock_capability_probe.return_value = mock_capability_nvidia
        mock_detect_system.return_value = None
        mock_auto_recover.return_value = None
        mock_is_installed.return_value = False
        mock_should_clean.return_value = False

        # User disabled dialog
        mock_config.gpu_pack_dialog_dont_show = True
        gpu_enabled = False

        # Call function
        result = show_gpu_pack_dialog_if_needed(mock_config, gpu_enabled)

        # Verify dialog was NOT shown
        assert result is None, "Dialog should NOT have been shown when user suppressed it"
        mock_dialog_class.assert_not_called()

    @patch('utils.gpu_pack_cleaner.should_clean_on_startup')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.capability_probe')
    @patch('utils.gpu_startup_logger.is_gpu_pack_installed')
    @patch('ui.gpu_download_dialog.GpuPackDownloadDialog')
    def test_dialog_shown_when_prefer_system_pytorch_disabled(
        self,
        mock_dialog_class,
        mock_is_installed,
        mock_capability_probe,
        mock_detect_system,
        mock_auto_recover,
        mock_should_clean,
        mock_config,
        mock_capability_nvidia
    ):
        """Dialog SHOULD appear: prefer_system_pytorch=False ignores system CUDA."""
        from utils.gpu_startup_logger import show_gpu_pack_dialog_if_needed

        # Setup mocks
        mock_capability_probe.return_value = mock_capability_nvidia
        mock_detect_system.return_value = {
            'torch_version': '2.0.0',
            'cuda_version': '12.1'
        }
        mock_auto_recover.return_value = None
        mock_is_installed.return_value = False
        mock_should_clean.return_value = False

        mock_dialog_instance = Mock()
        mock_dialog_class.return_value = mock_dialog_instance

        # User disabled prefer_system_pytorch
        mock_config.prefer_system_pytorch = False
        gpu_enabled = False

        # Call function
        result = show_gpu_pack_dialog_if_needed(mock_config, gpu_enabled)

        # Verify dialog WAS shown (system check skipped)
        assert result is not None, "Dialog should have been shown when prefer_system_pytorch=False"
        mock_dialog_class.assert_called_once_with(mock_config)
        mock_dialog_instance.show.assert_called_once()

    @patch('utils.gpu_pack_cleaner.should_clean_on_startup')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.capability_probe')
    @patch('utils.gpu_startup_logger.is_gpu_pack_installed')
    @patch('ui.gpu_download_dialog.GpuPackDownloadDialog')
    def test_dialog_exception_handled_gracefully(
        self,
        mock_dialog_class,
        mock_is_installed,
        mock_capability_probe,
        mock_detect_system,
        mock_auto_recover,
        mock_should_clean,
        mock_config,
        mock_capability_nvidia
    ):
        """Dialog creation exception should be handled gracefully."""
        from utils.gpu_startup_logger import show_gpu_pack_dialog_if_needed

        # Setup mocks
        mock_capability_probe.return_value = mock_capability_nvidia
        mock_detect_system.return_value = None
        mock_auto_recover.return_value = None
        mock_is_installed.return_value = False
        mock_should_clean.return_value = False

        # Dialog creation raises exception
        mock_dialog_class.side_effect = Exception("Dialog creation failed")

        gpu_enabled = False

        # Call function - should not raise
        result = show_gpu_pack_dialog_if_needed(mock_config, gpu_enabled)

        # Verify function handled exception and returned None
        assert result is None, "Function should return None when dialog creation fails"
        mock_dialog_class.assert_called_once()