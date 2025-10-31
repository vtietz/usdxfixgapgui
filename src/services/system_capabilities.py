"""
System capabilities detection service.

Single source of truth for:
- PyTorch availability (CPU/GPU)
- CUDA/GPU detection
- FFmpeg availability
- Detection method availability

This service is initialized once at application startup and provides
a consistent API for capability queries throughout the application.
"""

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Optional

# Conditionally import Qt - not needed for CLI mode
try:
    from PySide6.QtCore import QObject, Signal

    HAS_QT = True
except ImportError:
    HAS_QT = False

    # Dummy implementations for CLI mode
    class QObject:
        pass

    class Signal:
        def __init__(self, *args):
            pass

        def emit(self, *args):
            pass


logger = logging.getLogger(__name__)


@dataclass
class SystemCapabilities:
    """
    Immutable snapshot of system capabilities.

    Attributes:
        has_torch: PyTorch is importable
        torch_version: PyTorch version string if available
        torch_error: Error message if torch import failed
        has_cuda: CUDA is available via PyTorch
        cuda_version: CUDA version string if available
        gpu_name: GPU device name if available
        has_ffmpeg: FFmpeg executable found in PATH
        has_ffprobe: FFprobe executable found in PATH
        ffmpeg_version: FFmpeg version string if available
        can_detect: At least one detection method available (requires torch + ffmpeg)
    """

    # PyTorch
    has_torch: bool
    torch_version: Optional[str]
    torch_error: Optional[str]

    # CUDA/GPU
    has_cuda: bool
    cuda_version: Optional[str]
    gpu_name: Optional[str]

    # FFmpeg
    has_ffmpeg: bool
    has_ffprobe: bool
    ffmpeg_version: Optional[str]

    # Detection availability
    can_detect: bool

    def get_status_summary(self) -> str:
        """Get human-readable status summary for logging."""
        lines = []
        lines.append("System Capabilities:")
        lines.append(f"  PyTorch: {'✓' if self.has_torch else '✗'} {self.torch_version or self.torch_error or 'N/A'}")
        if self.has_torch:
            lines.append(f"  CUDA: {'✓' if self.has_cuda else '✗'} {self.cuda_version or 'N/A'}")
            if self.has_cuda and self.gpu_name:
                lines.append(f"  GPU: {self.gpu_name}")
        lines.append(f"  FFmpeg: {'✓' if self.has_ffmpeg else '✗'} {self.ffmpeg_version or 'N/A'}")
        lines.append(f"  FFprobe: {'✓' if self.has_ffprobe else '✗'}")
        lines.append(f"  Can detect gaps: {'✓' if self.can_detect else '✗'}")
        return "\n".join(lines)

    def get_detection_mode(self) -> str:
        """Get current detection mode: 'gpu', 'cpu', or 'unavailable'."""
        if not self.can_detect:
            return "unavailable"
        if self.has_cuda:
            return "gpu"
        return "cpu"

    def get_user_message(self) -> str:
        """Get user-friendly status message for UI."""
        if not self.has_torch:
            return f"❌ PyTorch not available: {self.torch_error or 'Unknown error'}"

        if not self.has_ffmpeg:
            return "❌ FFmpeg not available"

        if self.has_cuda:
            return f"✅ GPU acceleration available ({self.gpu_name})"

        return "✅ CPU detection available"


class SystemCapabilitiesService(QObject):
    """
    Service for checking and monitoring system capabilities.

    Singleton pattern - only one instance per application.
    Initialized once at startup, results cached.

    Signals:
        capabilities_changed: Emitted when capabilities change (e.g., GPU Pack installed)
    """

    # Signal emitted when capabilities change
    capabilities_changed = Signal(SystemCapabilities)

    # Singleton instance
    _instance: Optional["SystemCapabilitiesService"] = None

    def __new__(cls):
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize service (only runs once due to singleton)."""
        if self._initialized:
            return

        # Only call super().__init__() if we have real Qt
        if HAS_QT and isinstance(QObject, type):
            try:
                super().__init__()
            except RuntimeError:
                # Qt not available (e.g., headless environment)
                pass

        self._capabilities: Optional[SystemCapabilities] = None
        self._initialized = True
        logger.debug("SystemCapabilitiesService initialized")

    def check(self, log_callback: Optional[callable] = None) -> SystemCapabilities:
        """
        Check system capabilities (cached after first call).

        Args:
            log_callback: Optional callback for progress logging (e.g., splash screen)
                         Called with string messages like "Checking PyTorch..."

        Returns:
            SystemCapabilities with all detected features
        """
        if self._capabilities is not None:
            return self._capabilities

        logger.info("Starting system capability check...")

        if log_callback:
            log_callback("Checking PyTorch availability...")

        # Check PyTorch
        has_torch, torch_version, torch_error = self._check_torch()

        if log_callback:
            if has_torch:
                log_callback(f"✓ PyTorch {torch_version} loaded")
            else:
                log_callback(f"✗ PyTorch not available: {torch_error}")

        # Check CUDA (only if torch available)
        has_cuda = False
        cuda_version = None
        gpu_name = None

        if has_torch:
            if log_callback:
                log_callback("Checking CUDA availability...")
            has_cuda, cuda_version, gpu_name = self._check_cuda()
            if log_callback:
                if has_cuda:
                    log_callback(f"✓ CUDA {cuda_version} available ({gpu_name})")
                else:
                    # Don't show CUDA warning yet - will show unified GPU info later
                    pass

        # Even if CUDA not available, check for physical NVIDIA GPU hardware
        # This allows us to offer GPU Pack download
        if not gpu_name:
            gpu_name = self._check_physical_gpu()

        # Show GPU status in a unified way
        if log_callback and gpu_name:
            if has_cuda:
                # Already logged above with CUDA version
                pass
            else:
                # GPU detected but no CUDA - indicate GPU Pack available
                log_callback(f"⚠ GPU detected but not enabled: {gpu_name}")
                log_callback("  (GPU Pack required for acceleration)")
        elif log_callback and not has_cuda:
            # No GPU at all
            log_callback("ℹ No NVIDIA GPU detected (CPU mode)")

        # Check FFmpeg
        if log_callback:
            log_callback("Checking FFmpeg...")
        has_ffmpeg, ffmpeg_version = self._check_ffmpeg()
        has_ffprobe = self._check_ffprobe()

        if log_callback:
            if has_ffmpeg:
                log_callback(f"✓ FFmpeg {ffmpeg_version} found")
            else:
                log_callback("✗ FFmpeg not found")
            if has_ffprobe:
                log_callback("✓ FFprobe found")
            else:
                log_callback("✗ FFprobe not found")

        # Determine if detection is possible
        can_detect = has_torch and has_ffmpeg

        self._capabilities = SystemCapabilities(
            has_torch=has_torch,
            torch_version=torch_version,
            torch_error=torch_error,
            has_cuda=has_cuda,
            cuda_version=cuda_version,
            gpu_name=gpu_name,
            has_ffmpeg=has_ffmpeg,
            has_ffprobe=has_ffprobe,
            ffmpeg_version=ffmpeg_version,
            can_detect=can_detect,
        )

        logger.info(f"\n{self._capabilities.get_status_summary()}")

        return self._capabilities

    def get_capabilities(self) -> Optional[SystemCapabilities]:
        """
        Get cached capabilities without re-checking.

        Returns:
            Cached SystemCapabilities or None if check() not called yet
        """
        return self._capabilities

    def refresh(self, log_callback: Optional[callable] = None) -> SystemCapabilities:
        """
        Force re-check of capabilities (e.g., after GPU Pack installation).

        Emits capabilities_changed signal with new capabilities.

        Args:
            log_callback: Optional callback for progress logging

        Returns:
            Updated SystemCapabilities
        """
        logger.info("Refreshing system capabilities...")
        self._capabilities = None
        new_capabilities = self.check(log_callback)
        self.capabilities_changed.emit(new_capabilities)
        return new_capabilities

    def _check_torch(self) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if PyTorch is available.

        Returns:
            (has_torch, version, error_message)
        """
        try:
            import torch

            version = torch.__version__
            logger.debug(f"PyTorch {version} loaded successfully")
            return True, version, None
        except ImportError as e:
            error_msg = f"Import failed: {e}"
            logger.warning(f"PyTorch not available: {error_msg}")
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(f"PyTorch check failed: {error_msg}")
            return False, None, error_msg

    def _check_cuda(self) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check CUDA availability (requires torch already imported).

        Returns:
            (has_cuda, cuda_version, gpu_name)
        """
        try:
            import torch

            if torch.cuda.is_available():
                cuda_version = torch.version.cuda
                gpu_name = torch.cuda.get_device_name(0)
                logger.debug(f"CUDA {cuda_version} available: {gpu_name}")
                return True, cuda_version, gpu_name
            else:
                logger.debug("CUDA not available")
                return False, None, None
        except Exception as e:
            logger.debug(f"CUDA check failed: {e}")
            return False, None, None

    def _check_physical_gpu(self) -> Optional[str]:
        """
        Check for physical NVIDIA GPU hardware using nvidia-smi or NVML.
        This is separate from CUDA availability - detects GPU even without GPU Pack.

        Returns:
            GPU name if found, None otherwise
        """
        try:
            from utils.gpu_bootstrap import capability_probe

            cap = capability_probe()
            if cap and "gpu_names" in cap and cap["gpu_names"]:
                gpu_name = cap["gpu_names"][0] if isinstance(cap["gpu_names"], list) else cap["gpu_names"]
                logger.debug(f"Physical GPU detected: {gpu_name}")
                return gpu_name
        except Exception as e:
            logger.debug(f"Physical GPU detection failed: {e}")

        return None

    def _check_ffmpeg(self) -> tuple[bool, Optional[str]]:
        """
        Check if FFmpeg is available in PATH.

        Returns:
            (has_ffmpeg, version)
        """
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if result.returncode == 0:
                # Parse version from first line
                first_line = result.stdout.split("\n")[0]
                version = first_line.split("version")[1].split()[0] if "version" in first_line else "unknown"
                logger.debug(f"FFmpeg {version} found")
                return True, version
            else:
                logger.warning("FFmpeg command failed")
                return False, None
        except FileNotFoundError:
            logger.warning("FFmpeg not found in PATH")
            return False, None
        except Exception as e:
            logger.warning(f"FFmpeg check failed: {e}")
            return False, None

    def _check_ffprobe(self) -> bool:
        """
        Check if FFprobe is available in PATH.

        Returns:
            True if ffprobe found
        """
        try:
            result = subprocess.run(
                ["ffprobe", "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if result.returncode == 0:
                logger.debug("FFprobe found")
                return True
            else:
                logger.warning("FFprobe command failed")
                return False
        except FileNotFoundError:
            logger.warning("FFprobe not found in PATH")
            return False
        except Exception as e:
            logger.warning(f"FFprobe check failed: {e}")
            return False


# Singleton instance for easy access
_service = SystemCapabilitiesService()


def check_system_capabilities(log_callback: Optional[callable] = None) -> SystemCapabilities:
    """
    Convenience function to check system capabilities.

    Args:
        log_callback: Optional callback for progress logging

    Returns:
        SystemCapabilities with all detected features
    """
    return _service.check(log_callback)


def get_capabilities() -> Optional[SystemCapabilities]:
    """
    Convenience function to get cached capabilities.

    Returns:
        Cached SystemCapabilities or None if not checked yet
    """
    return _service.get_capabilities()


def refresh_capabilities(log_callback: Optional[callable] = None) -> SystemCapabilities:
    """
    Convenience function to refresh capabilities.

    Args:
        log_callback: Optional callback for progress logging

    Returns:
        Updated SystemCapabilities
    """
    return _service.refresh(log_callback)
