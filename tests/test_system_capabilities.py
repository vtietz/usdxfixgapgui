"""
Tests for SystemCapabilitiesService.

Verifies capability detection, caching, and refresh behavior.
"""

import pytest
from unittest.mock import patch, MagicMock
from services.system_capabilities import SystemCapabilitiesService, SystemCapabilities, check_system_capabilities


@pytest.fixture
def fresh_service():
    """Create a fresh service instance for each test."""
    # Reset singleton
    SystemCapabilitiesService._instance = None
    service = SystemCapabilitiesService()
    yield service
    # Cleanup
    SystemCapabilitiesService._instance = None


class TestSystemCapabilities:
    """Test SystemCapabilities dataclass."""

    def test_get_status_summary_all_available(self):
        """Test status summary when all features available."""
        caps = SystemCapabilities(
            has_torch=True,
            torch_version="2.0.0",
            torch_error=None,
            has_cuda=True,
            cuda_version="12.1",
            gpu_name="NVIDIA RTX 3060",
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=True,
        )

        summary = caps.get_status_summary()
        assert "PyTorch: ✓ 2.0.0" in summary
        assert "CUDA: ✓ 12.1" in summary
        assert "GPU: NVIDIA RTX 3060" in summary
        assert "FFmpeg: ✓ 6.0" in summary
        assert "Can detect gaps: ✓" in summary

    def test_get_status_summary_torch_missing(self):
        """Test status summary when torch missing."""
        caps = SystemCapabilities(
            has_torch=False,
            torch_version=None,
            torch_error="No module named 'torch'",
            has_cuda=False,
            cuda_version=None,
            gpu_name=None,
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=False,
        )

        summary = caps.get_status_summary()
        assert "PyTorch: ✗" in summary
        assert "No module named 'torch'" in summary
        assert "Can detect gaps: ✗" in summary

    def test_get_detection_mode_gpu(self):
        """Test detection mode when GPU available."""
        caps = SystemCapabilities(
            has_torch=True,
            torch_version="2.0.0",
            torch_error=None,
            has_cuda=True,
            cuda_version="12.1",
            gpu_name="RTX 3060",
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=True,
        )
        assert caps.get_detection_mode() == "gpu"

    def test_get_detection_mode_cpu(self):
        """Test detection mode when only CPU available."""
        caps = SystemCapabilities(
            has_torch=True,
            torch_version="2.0.0",
            torch_error=None,
            has_cuda=False,
            cuda_version=None,
            gpu_name=None,
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=True,
        )
        assert caps.get_detection_mode() == "cpu"

    def test_get_detection_mode_unavailable(self):
        """Test detection mode when torch missing."""
        caps = SystemCapabilities(
            has_torch=False,
            torch_version=None,
            torch_error="Missing",
            has_cuda=False,
            cuda_version=None,
            gpu_name=None,
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=False,
        )
        assert caps.get_detection_mode() == "unavailable"

    def test_get_user_message_gpu_available(self):
        """Test user message when GPU available."""
        caps = SystemCapabilities(
            has_torch=True,
            torch_version="2.0.0",
            torch_error=None,
            has_cuda=True,
            cuda_version="12.1",
            gpu_name="RTX 3060",
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=True,
        )
        message = caps.get_user_message()
        assert "GPU acceleration available" in message
        assert "RTX 3060" in message

    def test_get_user_message_cpu_only(self):
        """Test user message when CPU only."""
        caps = SystemCapabilities(
            has_torch=True,
            torch_version="2.0.0",
            torch_error=None,
            has_cuda=False,
            cuda_version=None,
            gpu_name=None,
            has_ffmpeg=True,
            has_ffprobe=True,
            ffmpeg_version="6.0",
            can_detect=True,
        )
        message = caps.get_user_message()
        assert "CPU detection available" in message


class TestSystemCapabilitiesService:
    """Test SystemCapabilitiesService singleton."""

    def test_singleton_pattern(self, fresh_service):
        """Test that only one instance exists."""
        service1 = SystemCapabilitiesService()
        service2 = SystemCapabilitiesService()
        assert service1 is service2

    @patch("services.system_capabilities.SystemCapabilitiesService._check_torch")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffmpeg")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffprobe")
    def test_check_caches_result(self, mock_ffprobe, mock_ffmpeg, mock_torch, fresh_service):
        """Test that check() caches result and doesn't re-check."""
        # Setup mocks
        mock_torch.return_value = (True, "2.0.0", None)
        mock_ffmpeg.return_value = (True, "6.0")
        mock_ffprobe.return_value = True

        # First call
        caps1 = fresh_service.check()

        # Second call
        caps2 = fresh_service.check()

        # Should return same object (cached)
        assert caps1 is caps2

        # Mocks should only be called once
        assert mock_torch.call_count == 1
        assert mock_ffmpeg.call_count == 1
        assert mock_ffprobe.call_count == 1

    @patch("services.system_capabilities.SystemCapabilitiesService._check_torch")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_cuda")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffmpeg")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffprobe")
    def test_check_with_log_callback(self, mock_ffprobe, mock_ffmpeg, mock_cuda, mock_torch, fresh_service):
        """Test that log_callback is called during check."""
        # Setup mocks
        mock_torch.return_value = (True, "2.0.0", None)
        mock_cuda.return_value = (True, "12.1", "RTX 3060")
        mock_ffmpeg.return_value = (True, "6.0")
        mock_ffprobe.return_value = True

        log_messages = []

        def log_callback(msg):
            log_messages.append(msg)

        fresh_service.check(log_callback)

        # Verify log messages were called
        assert len(log_messages) > 0
        assert any("PyTorch" in msg for msg in log_messages)
        assert any("CUDA" in msg for msg in log_messages)
        assert any("FFmpeg" in msg for msg in log_messages)

    @patch("services.system_capabilities.SystemCapabilitiesService._check_torch")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffmpeg")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffprobe")
    def test_refresh_clears_cache(self, mock_ffprobe, mock_ffmpeg, mock_torch, fresh_service):
        """Test that refresh() re-checks capabilities."""
        # Setup mocks
        mock_torch.return_value = (True, "2.0.0", None)
        mock_ffmpeg.return_value = (True, "6.0")
        mock_ffprobe.return_value = True

        # First check
        caps1 = fresh_service.check()
        assert mock_torch.call_count == 1

        # Refresh (should re-check)
        caps2 = fresh_service.refresh()
        assert mock_torch.call_count == 2

        # Should return new object
        assert caps1 is not caps2

    @patch("services.system_capabilities.SystemCapabilitiesService._check_torch")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffmpeg")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffprobe")
    def test_refresh_emits_signal(self, mock_ffprobe, mock_ffmpeg, mock_torch, fresh_service, qtbot):
        """Test that refresh() emits capabilities_changed signal."""
        # Setup mocks
        mock_torch.return_value = (True, "2.0.0", None)
        mock_ffmpeg.return_value = (True, "6.0")
        mock_ffprobe.return_value = True

        # Connect signal spy
        with qtbot.waitSignal(fresh_service.capabilities_changed, timeout=1000):
            fresh_service.refresh()

    def test_get_capabilities_before_check(self, fresh_service):
        """Test get_capabilities() returns None before check()."""
        assert fresh_service.get_capabilities() is None

    @patch("services.system_capabilities.SystemCapabilitiesService._check_torch")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffmpeg")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffprobe")
    def test_get_capabilities_after_check(self, mock_ffprobe, mock_ffmpeg, mock_torch, fresh_service):
        """Test get_capabilities() returns cached result after check()."""
        # Setup mocks
        mock_torch.return_value = (True, "2.0.0", None)
        mock_ffmpeg.return_value = (True, "6.0")
        mock_ffprobe.return_value = True

        caps1 = fresh_service.check()
        caps2 = fresh_service.get_capabilities()

        assert caps1 is caps2


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @patch("services.system_capabilities.SystemCapabilitiesService._check_torch")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffmpeg")
    @patch("services.system_capabilities.SystemCapabilitiesService._check_ffprobe")
    def test_check_system_capabilities(self, mock_ffprobe, mock_ffmpeg, mock_torch):
        """Test check_system_capabilities() convenience function."""
        # Reset singleton
        SystemCapabilitiesService._instance = None

        # Setup mocks
        mock_torch.return_value = (True, "2.0.0", None)
        mock_ffmpeg.return_value = (True, "6.0")
        mock_ffprobe.return_value = True

        caps = check_system_capabilities()

        assert caps.has_torch is True
        assert caps.has_ffmpeg is True

        # Cleanup
        SystemCapabilitiesService._instance = None

    def test_get_capabilities_convenience(self):
        """Test get_capabilities() convenience function."""
        # Reset singleton
        SystemCapabilitiesService._instance = None

        # Create fresh instance
        service = SystemCapabilitiesService()

        # Before check
        assert service.get_capabilities() is None

        # Cleanup
        SystemCapabilitiesService._instance = None


class TestCheckMethods:
    """Test individual check methods."""

    def test_check_torch_success(self, fresh_service):
        """Test _check_torch() when torch available (integration test)."""
        # This is an integration test - it tests with real torch
        has_torch, version, error = fresh_service._check_torch()

        # Should succeed since torch is in requirements.txt
        assert has_torch is True
        assert version is not None
        assert error is None

    def test_check_torch_import_error(self, fresh_service):
        """Test _check_torch() when torch missing."""

        def mock_import(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("No module named 'torch'")
            return __builtins__.__import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            has_torch, version, error = fresh_service._check_torch()

        assert has_torch is False
        assert version is None
        assert "Import failed" in error

    @patch("subprocess.run")
    def test_check_ffmpeg_success(self, mock_run, fresh_service):
        """Test _check_ffmpeg() when ffmpeg available."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ffmpeg version 6.0 Copyright (c) 2000-2023")

        has_ffmpeg, version = fresh_service._check_ffmpeg()

        assert has_ffmpeg is True
        assert version == "6.0"

    @patch("subprocess.run")
    def test_check_ffmpeg_not_found(self, mock_run, fresh_service):
        """Test _check_ffmpeg() when ffmpeg not in PATH."""
        mock_run.side_effect = FileNotFoundError()

        has_ffmpeg, version = fresh_service._check_ffmpeg()

        assert has_ffmpeg is False
        assert version is None

    @patch("subprocess.run")
    def test_check_ffprobe_success(self, mock_run, fresh_service):
        """Test _check_ffprobe() when ffprobe available."""
        mock_run.return_value = MagicMock(returncode=0)

        has_ffprobe = fresh_service._check_ffprobe()

        assert has_ffprobe is True

    @patch("subprocess.run")
    def test_check_ffprobe_not_found(self, mock_run, fresh_service):
        """Test _check_ffprobe() when ffprobe not in PATH."""
        mock_run.side_effect = FileNotFoundError()

        has_ffprobe = fresh_service._check_ffprobe()

        assert has_ffprobe is False
