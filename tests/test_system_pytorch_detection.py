"""
Tests for system PyTorch+CUDA detection functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestDetectSystemPytorchCuda:
    """Tests for detect_system_pytorch_cuda() function."""

    @patch('utils.gpu_bootstrap.torch')
    def test_detects_system_pytorch_with_cuda(self, mock_torch):
        """System PyTorch with CUDA 12.1 should be detected."""
        from utils.gpu_bootstrap import detect_system_pytorch_cuda

        # Mock PyTorch with CUDA available
        mock_torch.__version__ = "2.4.1+cu121"
        mock_torch.cuda.is_available.return_value = True
        mock_torch.version.cuda = "12.1"
        mock_torch.cuda.get_device_name.return_value = "NVIDIA GeForce RTX 4090"

        result = detect_system_pytorch_cuda()

        assert result is not None
        assert result['torch_version'] == "2.4.1+cu121"
        assert result['cuda_version'] == "12.1"
        assert result['device_name'] == "NVIDIA GeForce RTX 4090"

    @patch('utils.gpu_bootstrap.torch')
    def test_returns_none_when_cuda_not_available(self, mock_torch):
        """CPU-only PyTorch should return None."""
        from utils.gpu_bootstrap import detect_system_pytorch_cuda

        # Mock PyTorch without CUDA
        mock_torch.__version__ = "2.7.1+cpu"
        mock_torch.cuda.is_available.return_value = False

        result = detect_system_pytorch_cuda()

        assert result is None

    def test_returns_none_when_pytorch_not_installed(self):
        """Should return None when PyTorch not available."""
        from utils.gpu_bootstrap import detect_system_pytorch_cuda

        # Patch import to raise ImportError
        with patch.dict('sys.modules', {'torch': None}):
            with patch('utils.gpu_bootstrap.torch', side_effect=ImportError("No module named 'torch'")):
                result = detect_system_pytorch_cuda()

        assert result is None

    @patch('utils.gpu_bootstrap.torch')
    def test_returns_none_for_old_pytorch_version(self, mock_torch):
        """PyTorch 1.x should return None (too old)."""
        from utils.gpu_bootstrap import detect_system_pytorch_cuda

        # Mock old PyTorch version
        mock_torch.__version__ = "1.13.1+cu117"
        mock_torch.cuda.is_available.return_value = True
        mock_torch.version.cuda = "11.7"

        result = detect_system_pytorch_cuda()

        assert result is None

    @patch('utils.gpu_bootstrap.torch')
    def test_returns_none_when_cuda_version_is_none(self, mock_torch):
        """Should return None if cuda version is None."""
        from utils.gpu_bootstrap import detect_system_pytorch_cuda

        # Mock PyTorch with None CUDA version
        mock_torch.__version__ = "2.4.1"
        mock_torch.cuda.is_available.return_value = True
        mock_torch.version.cuda = None

        result = detect_system_pytorch_cuda()

        assert result is None

    @patch('utils.gpu_bootstrap.torch')
    def test_handles_device_name_error_gracefully(self, mock_torch):
        """Should handle device name error and use default."""
        from utils.gpu_bootstrap import detect_system_pytorch_cuda

        # Mock PyTorch with CUDA but device name fails
        mock_torch.__version__ = "2.4.1+cu121"
        mock_torch.cuda.is_available.return_value = True
        mock_torch.version.cuda = "12.1"
        mock_torch.cuda.get_device_name.side_effect = RuntimeError("CUDA error")

        result = detect_system_pytorch_cuda()

        assert result is not None
        assert result['torch_version'] == "2.4.1+cu121"
        assert result['cuda_version'] == "12.1"
        assert result['device_name'] == "Unknown GPU"

    @patch('utils.gpu_bootstrap.torch')
    def test_handles_different_cuda_versions(self, mock_torch):
        """Should detect various CUDA 12.x versions."""
        from utils.gpu_bootstrap import detect_system_pytorch_cuda

        test_cases = [
            ("2.4.1+cu121", "12.1"),
            ("2.4.1+cu124", "12.4"),
            ("2.5.0+cu126", "12.6"),
        ]

        for torch_version, cuda_version in test_cases:
            mock_torch.__version__ = torch_version
            mock_torch.cuda.is_available.return_value = True
            mock_torch.version.cuda = cuda_version
            mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 4090"

            result = detect_system_pytorch_cuda()

            assert result is not None, f"Failed for {torch_version}"
            assert result['torch_version'] == torch_version
            assert result['cuda_version'] == cuda_version


class TestBootstrapWithSystemPytorch:
    """Tests for bootstrap logic preferring system PyTorch."""

    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.validate_cuda_torch')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    def test_uses_system_pytorch_when_available_and_preferred(
        self, mock_recover, mock_validate, mock_detect
    ):
        """Should use system PyTorch when prefer_system_pytorch=true and validation succeeds."""
        from utils.gpu_bootstrap import bootstrap_and_maybe_enable_gpu

        # Mock config
        config = Mock()
        config.gpu_opt_in = None  # Not explicitly set
        config.prefer_system_pytorch = True
        config.gpu_pack_path = ''
        config.save_config = Mock()

        # Mock system PyTorch detection
        mock_detect.return_value = {
            'torch_version': '2.4.1+cu121',
            'cuda_version': '12.1',
            'device_name': 'NVIDIA RTX 4090'
        }

        # Mock validation success
        mock_validate.return_value = (True, "")

        result = bootstrap_and_maybe_enable_gpu(config)

        assert result is True
        assert config.gpu_last_health == "healthy (system)"
        assert config.gpu_last_error == ""
        mock_detect.assert_called_once()
        mock_validate.assert_called_once()

    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    def test_skips_system_pytorch_when_prefer_is_false(self, mock_recover, mock_detect):
        """Should skip system PyTorch detection when prefer_system_pytorch=false."""
        from utils.gpu_bootstrap import bootstrap_and_maybe_enable_gpu

        # Mock config
        config = Mock()
        config.gpu_opt_in = False  # Explicitly disabled
        config.prefer_system_pytorch = False
        config.gpu_pack_path = ''
        config.save_config = Mock()

        result = bootstrap_and_maybe_enable_gpu(config)

        # Should not call detect when GPU is disabled
        mock_detect.assert_not_called()
        assert result is False

    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.validate_cuda_torch')
    @patch('utils.gpu_bootstrap.enable_gpu_runtime')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    def test_falls_back_to_gpu_pack_when_system_pytorch_validation_fails(
        self, mock_recover, mock_enable_runtime, mock_validate, mock_detect
    ):
        """Should fall back to GPU Pack when system PyTorch validation fails."""
        from utils.gpu_bootstrap import bootstrap_and_maybe_enable_gpu
        from pathlib import Path

        # Mock config with GPU Pack installed
        config = Mock()
        config.gpu_opt_in = None
        config.prefer_system_pytorch = True
        config.gpu_pack_path = str(Path.home() / '.local/share/USDXFixGap/gpu_runtime/v1.4.0-cu121')
        config.gpu_flavor = 'cu121'
        config.save_config = Mock()

        # Mock system PyTorch detected but validation fails
        mock_detect.return_value = {
            'torch_version': '2.4.1+cu121',
            'cuda_version': '12.1',
            'device_name': 'NVIDIA RTX 4090'
        }

        # First call (system PyTorch): validation fails
        # Second call (GPU Pack): validation succeeds
        mock_validate.side_effect = [
            (False, "Smoke test failed"),  # System PyTorch validation fails
            (True, "")  # GPU Pack validation succeeds
        ]

        # Mock GPU Pack exists and enables successfully
        with patch('utils.gpu_bootstrap.Path') as mock_path_class:
            mock_pack_dir = Mock()
            mock_pack_dir.exists.return_value = True
            mock_path_class.return_value = mock_pack_dir

            mock_enable_runtime.return_value = True

            result = bootstrap_and_maybe_enable_gpu(config)

        assert result is True
        assert config.gpu_last_health == "healthy"
        assert mock_detect.call_count == 1  # System detection attempted
        assert mock_validate.call_count == 2  # System + GPU Pack validation


class TestStartupDialogWithSystemPytorch:
    """Tests for startup dialog skipping when system PyTorch available."""

    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    def test_skips_dialog_when_system_pytorch_available(self, mock_recover, mock_detect):
        """Should not show dialog when system PyTorch+CUDA detected."""
        from utils.gpu_startup_logger import show_gpu_pack_dialog_if_needed

        # Mock config
        config = Mock()
        config.prefer_system_pytorch = True
        config.gpu_pack_dialog_dont_show = False

        # Mock system PyTorch detection
        mock_detect.return_value = {
            'torch_version': '2.4.1+cu121',
            'cuda_version': '12.1',
            'device_name': 'NVIDIA RTX 4090'
        }

        result = show_gpu_pack_dialog_if_needed(config, gpu_enabled=False)

        assert result is None
        mock_detect.assert_called_once()

    @patch('utils.gpu_bootstrap.detect_system_pytorch_cuda')
    @patch('utils.gpu_bootstrap.capability_probe')
    @patch('utils.gpu_bootstrap.auto_recover_gpu_pack_config')
    @patch('utils.gpu_utils.is_gpu_pack_installed')
    @patch('ui.gpu_download_dialog.GpuPackDownloadDialog')
    def test_shows_dialog_when_system_pytorch_not_available(
        self, mock_dialog_class, mock_is_installed, mock_recover, mock_capability, mock_detect
    ):
        """Should show dialog when system PyTorch not available and GPU detected."""
        from utils.gpu_startup_logger import show_gpu_pack_dialog_if_needed

        # Mock config
        config = Mock()
        config.prefer_system_pytorch = True
        config.gpu_pack_dialog_dont_show = False

        # Mock no system PyTorch
        mock_detect.return_value = None

        # Mock NVIDIA GPU detected
        mock_capability.return_value = {
            'has_nvidia': True,
            'driver_version': '576.80',
            'gpu_names': ['NVIDIA RTX 4090']
        }

        # Mock no GPU Pack installed
        mock_is_installed.return_value = False

        # Mock dialog
        mock_dialog_instance = Mock()
        mock_dialog_class.return_value = mock_dialog_instance

        result = show_gpu_pack_dialog_if_needed(config, gpu_enabled=False)

        assert result == mock_dialog_instance
        mock_dialog_instance.show.assert_called_once()
