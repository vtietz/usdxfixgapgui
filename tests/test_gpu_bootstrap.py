"""
Tests for GPU Bootstrap

Tests staged runtime activation: layout detection, path calculation,
installation, and validation phases.
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch

from utils.gpu_bootstrap import (
    LayoutDetector,
    PackLayout,
    PathCalculator,
    PathConfig,
    PathInstaller,
    RuntimeValidator,
    enable_runtime,
    find_installed_pack_dirs,
    select_best_existing_pack,
    auto_recover_gpu_pack_config,
)


class TestLayoutDetector:
    """Test layout detection phase."""

    def test_detect_wheel_extraction(self, tmp_path):
        """Detect wheel extraction layout (torch/ at root)."""
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()
        (pack_dir / "torch").mkdir()

        layout = LayoutDetector.detect(pack_dir)
        assert layout == PackLayout.WHEEL_EXTRACTION

    def test_detect_site_packages(self, tmp_path):
        """Detect site-packages layout."""
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()
        (pack_dir / "site-packages").mkdir()

        layout = LayoutDetector.detect(pack_dir)
        assert layout == PackLayout.SITE_PACKAGES

    def test_detect_unknown_layout(self, tmp_path):
        """Detect unknown layout (neither structure present)."""
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()

        layout = LayoutDetector.detect(pack_dir)
        assert layout == PackLayout.UNKNOWN

    def test_detect_nonexistent_directory(self, tmp_path):
        """Detect layout for nonexistent directory."""
        pack_dir = tmp_path / "nonexistent"

        layout = LayoutDetector.detect(pack_dir)
        assert layout == PackLayout.UNKNOWN


class TestPathCalculator:
    """Test path calculation phase."""

    @patch("sys.platform", "win32")
    def test_wheel_extraction_windows(self, tmp_path):
        """Calculate paths for wheel extraction on Windows."""
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()

        config = PathCalculator.calculate(pack_dir, PackLayout.WHEEL_EXTRACTION)

        assert pack_dir in config.sys_path_entries
        assert pack_dir / "torch" / "lib" in config.dll_directories
        assert pack_dir / "bin" in config.dll_directories
        assert pack_dir / "torchaudio" / "lib" in config.dll_directories
        assert len(config.ld_library_paths) == 0

    @patch("sys.platform", "linux")
    def test_wheel_extraction_linux(self, tmp_path):
        """Calculate paths for wheel extraction on Linux."""
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()

        config = PathCalculator.calculate(pack_dir, PackLayout.WHEEL_EXTRACTION)

        assert pack_dir in config.sys_path_entries
        assert len(config.dll_directories) == 0
        assert pack_dir / "torch" / "lib" in config.ld_library_paths

    @patch("sys.platform", "win32")
    def test_site_packages_windows(self, tmp_path):
        """Calculate paths for site-packages on Windows."""
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()

        config = PathCalculator.calculate(pack_dir, PackLayout.SITE_PACKAGES)

        assert pack_dir / "site-packages" in config.sys_path_entries
        assert pack_dir / "bin" in config.dll_directories
        assert pack_dir / "site-packages" / "torchaudio" / "lib" in config.dll_directories
        assert len(config.ld_library_paths) == 0

    @patch("sys.platform", "linux")
    def test_site_packages_linux(self, tmp_path):
        """Calculate paths for site-packages on Linux."""
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()

        config = PathCalculator.calculate(pack_dir, PackLayout.SITE_PACKAGES)

        assert pack_dir / "site-packages" in config.sys_path_entries
        assert len(config.dll_directories) == 0
        assert pack_dir / "lib" in config.ld_library_paths

    def test_unknown_layout(self, tmp_path):
        """Calculate paths for unknown layout returns empty config."""
        pack_dir = tmp_path / "pack"

        config = PathCalculator.calculate(pack_dir, PackLayout.UNKNOWN)

        assert len(config.sys_path_entries) == 0
        assert len(config.dll_directories) == 0
        assert len(config.ld_library_paths) == 0


class TestPathInstaller:
    """Test path installation phase."""

    def test_install_sys_path(self, tmp_path):
        """Install sys.path entries."""
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()

        config = PathConfig(sys_path_entries=[pack_dir], dll_directories=[], ld_library_paths=[])

        original_path = sys.path.copy()
        try:
            result = PathInstaller.install(config)

            assert result.success
            assert str(pack_dir) in sys.path
            assert sys.path.index(str(pack_dir)) == 0  # Inserted at front
        finally:
            sys.path = original_path

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    @patch("sys.platform", "win32")
    @patch("os.add_dll_directory")
    def test_install_dll_directories_windows(self, mock_add_dll, tmp_path):
        """Install DLL directories on Windows."""
        dll_dir = tmp_path / "bin"
        dll_dir.mkdir()

        config = PathConfig(sys_path_entries=[], dll_directories=[dll_dir], ld_library_paths=[])

        result = PathInstaller.install(config)

        assert result.success
        mock_add_dll.assert_called_once_with(str(dll_dir))
        assert str(dll_dir) in result.added_dll_dirs

    @patch("sys.platform", "win32")
    def test_install_dll_directories_missing_dir(self, tmp_path):
        """Skip nonexistent DLL directories on Windows."""
        dll_dir = tmp_path / "nonexistent"

        config = PathConfig(sys_path_entries=[], dll_directories=[dll_dir], ld_library_paths=[])

        with patch("os.add_dll_directory") as mock_add_dll:
            result = PathInstaller.install(config)

            assert result.success
            mock_add_dll.assert_not_called()
            assert len(result.added_dll_dirs) == 0

    @patch("sys.platform", "linux")
    def test_install_ld_library_path(self, tmp_path):
        """Install LD_LIBRARY_PATH on Linux."""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()

        config = PathConfig(sys_path_entries=[], dll_directories=[], ld_library_paths=[lib_dir])

        original_env = os.environ.get("LD_LIBRARY_PATH")
        try:
            result = PathInstaller.install(config)

            assert result.success
            assert str(lib_dir) in os.environ.get("LD_LIBRARY_PATH", "")
        finally:
            if original_env:
                os.environ["LD_LIBRARY_PATH"] = original_env
            else:
                os.environ.pop("LD_LIBRARY_PATH", None)

    @patch("sys.platform", "linux")
    def test_install_ld_library_path_append(self, tmp_path):
        """Append to existing LD_LIBRARY_PATH."""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()

        config = PathConfig(sys_path_entries=[], dll_directories=[], ld_library_paths=[lib_dir])

        original_env = os.environ.get("LD_LIBRARY_PATH")
        os.environ["LD_LIBRARY_PATH"] = "/existing/path"
        try:
            result = PathInstaller.install(config)

            assert result.success
            ld_path = os.environ.get("LD_LIBRARY_PATH", "")
            assert str(lib_dir) in ld_path
            assert "/existing/path" in ld_path
        finally:
            if original_env:
                os.environ["LD_LIBRARY_PATH"] = original_env
            else:
                os.environ.pop("LD_LIBRARY_PATH", None)


class TestRuntimeValidator:
    """Test runtime validation phase."""

    @patch("sys.platform", "win32")
    @patch("ctypes.WinDLL")
    def test_vcruntime_present_windows(self, mock_windll):
        """Check VC++ runtime DLLs present on Windows."""
        result = RuntimeValidator.check_vcruntime()
        assert result is True
        assert mock_windll.call_count == 2

    @patch("sys.platform", "win32")
    @patch("ctypes.WinDLL", side_effect=FileNotFoundError("DLL not found"))
    def test_vcruntime_missing_windows(self, mock_windll):
        """Check VC++ runtime DLLs missing on Windows."""
        result = RuntimeValidator.check_vcruntime()
        assert result is False

    @patch("sys.platform", "linux")
    def test_vcruntime_non_windows(self):
        """VC++ check returns True on non-Windows."""
        result = RuntimeValidator.check_vcruntime()
        assert result is True


class TestOrchestratorIntegration:
    """Integration tests for orchestrator function."""

    @patch("sys.platform", "win32")
    @patch("os.add_dll_directory")
    def test_enable_gpu_runtime_wheel_extraction(self, mock_add_dll, tmp_path):
        """Full workflow: wheel extraction layout."""
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()
        (pack_dir / "torch").mkdir()
        (pack_dir / "torch" / "lib").mkdir()
        (pack_dir / "bin").mkdir()

        original_path = sys.path.copy()
        original_env = os.environ.get("USDXFIXGAP_GPU_PACK_DIR")
        try:
            success, added_dirs = enable_runtime(pack_dir)

            assert success is True
            assert str(pack_dir) in sys.path
            assert len(added_dirs) == 2  # torch/lib and bin
            assert os.environ.get("USDXFIXGAP_GPU_PACK_DIR") == str(pack_dir)
        finally:
            sys.path = original_path
            if original_env:
                os.environ["USDXFIXGAP_GPU_PACK_DIR"] = original_env
            else:
                os.environ.pop("USDXFIXGAP_GPU_PACK_DIR", None)

    @patch("sys.platform", "linux")
    def test_enable_gpu_runtime_site_packages_linux(self, tmp_path):
        """Full workflow: site-packages layout on Linux."""
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()
        (pack_dir / "site-packages").mkdir()
        (pack_dir / "lib").mkdir()

        original_path = sys.path.copy()
        original_env_pack = os.environ.get("USDXFIXGAP_GPU_PACK_DIR")
        original_env_ld = os.environ.get("LD_LIBRARY_PATH")
        try:
            success, added_dirs = enable_runtime(pack_dir)

            assert success is True
            assert str(pack_dir / "site-packages") in sys.path
            assert len(added_dirs) == 0  # No DLLs on Linux
            assert str(pack_dir / "lib") in os.environ.get("LD_LIBRARY_PATH", "")
            assert os.environ.get("USDXFIXGAP_GPU_PACK_DIR") == str(pack_dir)
        finally:
            sys.path = original_path
            if original_env_pack:
                os.environ["USDXFIXGAP_GPU_PACK_DIR"] = original_env_pack
            else:
                os.environ.pop("USDXFIXGAP_GPU_PACK_DIR", None)
            if original_env_ld:
                os.environ["LD_LIBRARY_PATH"] = original_env_ld
            else:
                os.environ.pop("LD_LIBRARY_PATH", None)

    def test_enable_gpu_runtime_unknown_layout(self, tmp_path):
        """Full workflow: unknown layout fails gracefully."""
        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()  # No torch/ or site-packages/

        success, added_dirs = enable_runtime(pack_dir)

        assert success is False
        assert len(added_dirs) == 0

    def test_enable_gpu_runtime_nonexistent_directory(self, tmp_path):
        """Full workflow: nonexistent directory fails gracefully."""
        pack_dir = tmp_path / "nonexistent"

        success, added_dirs = enable_runtime(pack_dir)

        assert success is False
        assert len(added_dirs) == 0


class TestFeatureFlagIntegration:
    """Test feature flag routing in original function."""

    @patch("utils.gpu_bootstrap.enable_runtime")
    def test_feature_flag_enabled(self, mock_refactored, tmp_path):
        """Test routing to refactored implementation when flag enabled."""
        # Import the actual .py file, not the module directory
        import importlib.util

        spec = importlib.util.spec_from_file_location("gpu_bootstrap_file", "src/utils/gpu_bootstrap.py")
        gpu_bootstrap_file = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gpu_bootstrap_file)
        enable_gpu_runtime = gpu_bootstrap_file.enable_gpu_runtime

        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()
        (pack_dir / "torch").mkdir()

        # Mock config with feature flag enabled
        mock_config = Mock()
        mock_config.experimental = Mock()
        mock_config.experimental.staged_gpu_bootstrap = True

        # Mock successful refactored call
        mock_refactored.return_value = (True, ["/dll/dir"])

        result = enable_gpu_runtime(pack_dir, mock_config)

        assert result is True
        mock_refactored.assert_called_once_with(pack_dir)

    def test_feature_flag_disabled(self, tmp_path):
        """Test fallback to legacy implementation when flag disabled."""
        # Import the actual .py file, not the module directory
        import importlib.util

        spec = importlib.util.spec_from_file_location("gpu_bootstrap_file", "src/utils/gpu_bootstrap.py")
        gpu_bootstrap_file = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gpu_bootstrap_file)
        enable_gpu_runtime = gpu_bootstrap_file.enable_gpu_runtime

        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()
        (pack_dir / "torch").mkdir()
        (pack_dir / "torch" / "lib").mkdir()

        # Mock config with feature flag disabled
        mock_config = Mock()
        mock_config.experimental = Mock()
        mock_config.experimental.staged_gpu_bootstrap = False

        original_path = sys.path.copy()
        try:
            # Should use legacy implementation
            with patch("os.add_dll_directory"):
                result = enable_gpu_runtime(pack_dir, mock_config)
                assert result is True
        finally:
            sys.path = original_path

    def test_no_config_uses_legacy(self, tmp_path):
        """Test legacy implementation when config not provided."""
        # Import the actual .py file, not the module directory
        import importlib.util

        spec = importlib.util.spec_from_file_location("gpu_bootstrap_file", "src/utils/gpu_bootstrap.py")
        gpu_bootstrap_file = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gpu_bootstrap_file)
        enable_gpu_runtime = gpu_bootstrap_file.enable_gpu_runtime

        pack_dir = tmp_path / "pack"
        pack_dir.mkdir()
        (pack_dir / "torch").mkdir()
        (pack_dir / "torch" / "lib").mkdir()

        original_path = sys.path.copy()
        try:
            with patch("os.add_dll_directory"):
                result = enable_gpu_runtime(pack_dir)  # No config
                assert result is True
        finally:
            sys.path = original_path


class TestAutoRecovery:
    """Test GPU Pack auto-recovery functionality."""

    def test_find_installed_pack_dirs_empty(self, tmp_path):
        """Test finding packs when directory doesn't exist."""
        with patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path)}):
            candidates = find_installed_pack_dirs()
            assert len(candidates) == 0

    def test_find_installed_pack_dirs_with_valid_pack(self, tmp_path):
        """Test finding packs with valid folder structure."""
        runtime_root = tmp_path / "USDXFixGap" / "gpu_runtime"
        runtime_root.mkdir(parents=True)

        # Create a valid pack directory
        pack_dir = runtime_root / "v1.4.0-cu121"
        pack_dir.mkdir()

        with patch("utils.files.get_localappdata_dir", return_value=str(tmp_path / "USDXFixGap")):
            candidates = find_installed_pack_dirs()
            assert len(candidates) == 1
            assert candidates[0]["path"] == pack_dir
            assert candidates[0]["app_version"] == "1.4.0"
            assert candidates[0]["flavor"] == "cu121"
            assert candidates[0]["has_install_json"] is False

    def test_find_installed_pack_dirs_with_install_json(self, tmp_path):
        """Test finding packs with install.json."""
        runtime_root = tmp_path / "USDXFixGap" / "gpu_runtime"
        runtime_root.mkdir(parents=True)

        pack_dir = runtime_root / "v1.4.0-cu121"
        pack_dir.mkdir()

        # Create install.json
        install_json = pack_dir / "install.json"
        import json

        with open(install_json, "w") as f:
            json.dump({"app_version": "1.4.0", "flavor": "cu121", "torch_version": "2.1.0", "cuda_version": "12.1"}, f)

        with patch("utils.files.get_localappdata_dir", return_value=str(tmp_path / "USDXFixGap")):
            candidates = find_installed_pack_dirs()
            assert len(candidates) == 1
            assert candidates[0]["has_install_json"] is True
            assert candidates[0]["app_version"] == "1.4.0"
            assert candidates[0]["flavor"] == "cu121"

    def test_select_best_existing_pack_prefer_flavor(self, tmp_path):
        """Test pack selection prefers matching flavor."""
        candidates = [
            {"path": tmp_path / "v1.4.0-cu121", "app_version": "1.4.0", "flavor": "cu121", "has_install_json": False},
            {"path": tmp_path / "v1.4.0-cu124", "app_version": "1.4.0", "flavor": "cu124", "has_install_json": False},
        ]

        best = select_best_existing_pack(candidates, config_flavor="cu124")
        assert best == tmp_path / "v1.4.0-cu124"

    def test_select_best_existing_pack_prefer_install_json(self, tmp_path):
        """Test pack selection prefers packs with install.json."""
        candidates = [
            {"path": tmp_path / "v1.4.0-cu121", "app_version": "1.4.0", "flavor": "cu121", "has_install_json": False},
            {"path": tmp_path / "v1.3.0-cu121", "app_version": "1.3.0", "flavor": "cu121", "has_install_json": True},
        ]

        best = select_best_existing_pack(candidates, config_flavor="cu121")
        assert best == tmp_path / "v1.3.0-cu121"  # Prefers install.json

    def test_select_best_existing_pack_prefer_recent_version(self, tmp_path):
        """Test pack selection prefers most recent version."""
        candidates = [
            {"path": tmp_path / "v1.3.0-cu121", "app_version": "1.3.0", "flavor": "cu121", "has_install_json": True},
            {"path": tmp_path / "v1.4.0-cu121", "app_version": "1.4.0", "flavor": "cu121", "has_install_json": True},
        ]

        best = select_best_existing_pack(candidates, config_flavor="cu121")
        assert best == tmp_path / "v1.4.0-cu121"  # Newer version

    def test_auto_recover_gpu_pack_config_no_recovery_needed(self, tmp_path):
        """Test auto-recovery skips when pack path already set."""
        mock_config = Mock()
        mock_config.gpu_pack_path = "/existing/path"

        recovered = auto_recover_gpu_pack_config(mock_config)
        assert recovered is False

    def test_auto_recover_gpu_pack_config_successful_recovery(self, tmp_path):
        """Test successful auto-recovery updates config."""
        runtime_root = tmp_path / "USDXFixGap" / "gpu_runtime"
        runtime_root.mkdir(parents=True)

        pack_dir = runtime_root / "v1.4.0-cu121"
        pack_dir.mkdir()

        # Create install.json
        install_json = pack_dir / "install.json"
        import json

        with open(install_json, "w") as f:
            json.dump({"app_version": "1.4.0", "flavor": "cu121", "torch_version": "2.1.0", "cuda_version": "12.1"}, f)

        mock_config = Mock()
        mock_config.gpu_pack_path = ""
        mock_config.gpu_flavor = "cu121"
        mock_config.gpu_opt_in = False  # GPU not enabled initially

        with patch("utils.files.get_localappdata_dir", return_value=str(tmp_path / "USDXFixGap")):
            recovered = auto_recover_gpu_pack_config(mock_config)

        assert recovered is True
        assert mock_config.gpu_pack_path == str(pack_dir)
        assert mock_config.gpu_pack_installed_version == "1.4.0"
        assert mock_config.gpu_opt_in is True
        mock_config.save_config.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
