"""
Type Definitions for GPU Bootstrap

Strongly-typed result and configuration classes for GPU Pack activation.
Eliminates global mutable state and clarifies data flow.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List


@dataclass
class PathConfig:
    """Configuration for path additions needed by GPU Pack."""

    pack_dir: Path
    layout: str  # "wheel" | "site-packages" | "unknown"
    dll_dirs: List[Path] = field(default_factory=list)
    sys_path_entries: List[Path] = field(default_factory=list)
    ld_library_path_entries: List[Path] = field(default_factory=list)


@dataclass
class InstallationResult:
    """Result of path installation phase."""

    success: bool
    added_dll_dirs: List[str] = field(default_factory=list)
    added_sys_paths: List[str] = field(default_factory=list)
    added_ld_paths: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of torch/CUDA validation phase."""

    success: bool
    mode: str  # "cuda" | "cpu" | "none"
    error_message: Optional[str] = None
    torch_version: Optional[str] = None
    cuda_version: Optional[str] = None
    diagnostics: List[str] = field(default_factory=list)


@dataclass
class BootstrapResult:
    """Complete result of GPU bootstrap process."""

    success: bool
    mode: str  # "cuda" | "cpu" | "none"
    installation: Optional[InstallationResult] = None
    validation: Optional[ValidationResult] = None
    diagnostics: List[str] = field(default_factory=list)
    pack_dir: Optional[Path] = None

    def get_error_message(self) -> str:
        """Get consolidated error message from all phases."""
        errors = []

        if self.installation and self.installation.error_message:
            errors.append(f"Installation: {self.installation.error_message}")

        if self.validation and self.validation.error_message:
            errors.append(f"Validation: {self.validation.error_message}")

        if self.diagnostics:
            errors.extend(self.diagnostics)

        return " | ".join(errors) if errors else "No errors"


@dataclass
class GPUStatus:
    """Concise status object for high-level app usage.

    This is a simplified view derived from BootstrapResult so callers (e.g. main app)
    can make decisions without parsing multiple structures.
    """

    enabled: bool  # True if GPU (CUDA torch) validated
    source: str  # 'pack' | 'system' | 'cpu'
    cuda_available: bool  # torch.cuda.is_available() outcome when torch imported
    torch_version: Optional[str] = None
    cuda_version: Optional[str] = None
    error: Optional[str] = None
    pack_dir: Optional[Path] = None
    diagnostics: List[str] = field(default_factory=list)

    def as_structured_log(self) -> str:
        return (
            f"GPUStatus enabled={self.enabled} source={self.source} cuda_available={self.cuda_available} "
            f"torch_version={self.torch_version} cuda_version={self.cuda_version} pack_dir={self.pack_dir} "
            f"error={self.error} diagnostics={'||'.join(self.diagnostics) if self.diagnostics else 'none'}"
        )
