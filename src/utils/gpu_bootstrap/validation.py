"""
CUDA/Torchaudio Validation Helpers

Provide small, focused functions to validate torch CUDA availability and
torchaudio importability without pulling in other bootstrap code.
"""

import sys
from typing import Tuple


def validate_cuda_torch(expected_cuda: str = "12") -> Tuple[bool, str]:
    """
    Validate that torch.cuda is available and matches expected CUDA version.

    Args:
        expected_cuda: Expected CUDA version (e.g., "12.1" or "12" for any 12.x)

    Returns:
        Tuple of (success, error_message)
    """
    try:
        import torch  # type: ignore
    except (ImportError, OSError) as e:
        error_msg = f"PyTorch not importable: {e}"

        # Add Linux-specific guidance if libcublas error detected
        if sys.platform.startswith("linux") and "libcublas" in str(e).lower():
            error_msg += (
                "\n\nLinux GPU Pack requires system CUDA libraries."
                "\nInstall CUDA Toolkit 12.1+:"
                "\n  wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-keyring_1.1-1_all.deb"  # noqa: E501
                "\n  sudo dpkg -i cuda-keyring_1.1-1_all.deb"
                "\n  sudo apt-get update"
                "\n  sudo apt-get install cuda-toolkit-12-1"
                "\n\nOr use CPU mode (no CUDA toolkit needed)."
            )

        return False, error_msg
    except Exception as e:
        # Catch-all for unusual import environments (including missing CUDA libraries)
        error_msg = f"PyTorch import error: {e}"

        # Add Linux-specific guidance if libcublas error detected
        if sys.platform.startswith("linux") and "libcublas" in str(e).lower():
            error_msg += (
                "\n\nLinux GPU Pack requires system CUDA libraries."
                "\nInstall CUDA Toolkit 12.1+:"
                "\n  wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-keyring_1.1-1_all.deb"  # noqa: E501
                "\n  sudo dpkg -i cuda-keyring_1.1-1_all.deb"
                "\n  sudo apt-get update"
                "\n  sudo apt-get install cuda-toolkit-12-1"
                "\n\nOr use CPU mode (no CUDA toolkit needed)."
            )

        return False, error_msg

    try:
        if not torch.cuda.is_available():
            return False, "torch.cuda.is_available() returned False"

        cuda_version = torch.version.cuda
        if not cuda_version:
            return False, "CUDA version is None"

        # Check version match (allow "12" to match any 12.x)
        if not cuda_version.startswith(expected_cuda.split(".")[0]):
            return False, f"CUDA version mismatch: expected {expected_cuda}, got {cuda_version}"

        # Smoke test
        try:
            device = torch.device("cuda:0")
            test_tensor = torch.zeros(10, 10, device=device)
            result = test_tensor.sum().item()
            if result != 0.0:
                return False, f"CUDA smoke test failed: expected 0.0, got {result}"
        except Exception as e:  # Narrowing further risks hiding hardware-specific errors
            return False, f"CUDA smoke test error: {e}"

        return True, ""
    except Exception as e:
        return False, f"Failed to validate CUDA: {e}"


def validate_torchaudio() -> Tuple[bool, str]:
    """
    Validate that torchaudio can be imported and its DLLs load correctly.

    Returns:
        Tuple of (success, error_message)
    """
    try:
        import torchaudio  # type: ignore
    except (ImportError, OSError) as e:
        return False, f"torchaudio not importable: {e}"
    except Exception as e:
        return False, f"torchaudio import error: {e}"

    try:
        # Access a symbol requiring DLL load
        _ = torchaudio.transforms.Spectrogram
        return True, ""
    except Exception as e:
        return False, f"torchaudio import/DLL error: {e}"
