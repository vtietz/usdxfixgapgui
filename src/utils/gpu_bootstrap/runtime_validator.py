"""
Runtime Validation - Check Dependencies

Validates Visual C++ runtime availability on Windows.
"""

import sys
import logging

logger = logging.getLogger(__name__)


class RuntimeValidator:
    """Validate runtime dependencies."""

    @staticmethod
    def check_vcruntime() -> bool:
        """
        Check for Microsoft Visual C++ Redistributable DLLs on Windows.

        Returns:
            True if all required DLLs are present, False otherwise
        """
        if sys.platform != "win32":
            return True  # Not applicable on non-Windows

        try:
            import ctypes

            required_dlls = ["vcruntime140_1.dll", "msvcp140.dll"]
            missing_dlls = []

            for dll_name in required_dlls:
                try:
                    ctypes.WinDLL(dll_name)
                except (OSError, FileNotFoundError):
                    missing_dlls.append(dll_name)

            if missing_dlls:
                logger.warning(
                    f"Microsoft Visual C++ Redistributable DLLs missing: {', '.join(missing_dlls)}. "
                    "Install Visual Studio 2015-2022 (x64) runtime from: "
                    "https://aka.ms/vs/17/release/vc_redist.x64.exe"
                )
                return False

            return True

        except Exception as e:
            logger.debug(f"Could not check VC++ runtime: {e}")
            return True  # Don't fail on check errors
