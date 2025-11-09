"""
Tests for PyInstaller Runtime Hook (hook-rthook-gpu-pack.py)

Tests the GPU Pack runtime hook logic to prevent regressions.
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


# Import the hook functions directly
# Note: We can't import the hook file directly as it executes on import,
# so we'll load it manually for testing
def load_hook_module():
    """Load hook module for testing."""
    hook_file = Path(__file__).parent.parent / "scripts" / "hook-rthook-gpu-pack.py"

    # Read and compile the hook code (without the setup_gpu_pack() call at the end)
    with open(hook_file, "r") as f:
        hook_code = f.read()

    # Remove the final setup call for testing
    hook_code = hook_code.replace("# Execute setup\nsetup_gpu_pack()", "")

    # Create a module namespace and compile
    import types

    module = types.ModuleType("hook_rthook_gpu_pack")
    exec(compile(hook_code, str(hook_file), "exec"), module.__dict__)

    return module


@pytest.fixture
def hook_functions():
    """Fixture to load hook functions as dictionary."""
    module = load_hook_module()
    return module.__dict__


@pytest.fixture
def hook_module():
    """Fixture to load hook as module object."""
    return load_hook_module()


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory with config file."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def temp_gpu_pack(tmp_path):
    """Create temporary GPU Pack directory structure."""
    pack_dir = tmp_path / "gpu_pack"
    pack_dir.mkdir()
    torch_dir = pack_dir / "torch"
    torch_dir.mkdir()
    lib_dir = torch_dir / "lib"
    lib_dir.mkdir()
    return pack_dir


@pytest.fixture(autouse=True)
def clean_gpu_env():
    """Clean up GPU Pack environment variable before each test."""
    # Save original
    original = os.environ.get("USDXFIXGAP_GPU_PACK_DIR")

    # Clear before test
    os.environ.pop("USDXFIXGAP_GPU_PACK_DIR", None)

    yield

    # Restore after test
    if original:
        os.environ["USDXFIXGAP_GPU_PACK_DIR"] = original
    else:
        os.environ.pop("USDXFIXGAP_GPU_PACK_DIR", None)


class TestGetConfigDir:
    """Test get_config_dir function."""

    def test_windows_config_dir(self, hook_functions):
        """Test Windows config directory path."""
        with (
            patch("sys.platform", "win32"),
            patch.dict("os.environ", {"LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local"}),
        ):
            result = hook_functions["get_config_dir"]()
            assert result == Path("C:\\Users\\Test\\AppData\\Local\\USDXFixGap")

    def test_macos_config_dir(self, hook_functions):
        """Test macOS config directory path."""
        with patch("sys.platform", "darwin"), patch.object(Path, "home", return_value=Path("/Users/test")):
            result = hook_functions["get_config_dir"]()
            assert result == Path("/Users/test/Library/Application Support/USDXFixGap")

    def test_linux_config_dir_with_xdg(self, hook_functions):
        """Test Linux config directory with XDG_CONFIG_HOME."""
        with patch("sys.platform", "linux"), patch.dict("os.environ", {"XDG_CONFIG_HOME": "/home/test/.config"}):
            result = hook_functions["get_config_dir"]()
            assert result == Path("/home/test/.config/usdxfixgap")

    def test_linux_config_dir_without_xdg(self, hook_functions):
        """Test Linux config directory without XDG_CONFIG_HOME."""
        with (
            patch("sys.platform", "linux"),
            patch.dict("os.environ", {}, clear=True),
            patch.object(Path, "home", return_value=Path("/home/test")),
        ):
            result = hook_functions["get_config_dir"]()
            assert result == Path("/home/test/.config/usdxfixgap")


class TestReadGpuPackPath:
    """Test read_gpu_pack_path function."""

    def test_gpu_enabled_with_valid_path(self, hook_module, temp_config_dir, tmp_path):
        """Test reading GPU Pack path when GPU is enabled."""
        # Create actual GPU Pack directory
        gpu_pack = tmp_path / "gpu_pack"
        gpu_pack.mkdir()
        (gpu_pack / "torch").mkdir()

        config_file = temp_config_dir / "config.ini"
        config_file.write_text(
            f"""
[General]
gpu_opt_in = true
gpu_pack_path = {gpu_pack}
"""
        )

        result = hook_module.read_gpu_pack_path(config_file)
        assert result == gpu_pack

    def test_gpu_disabled(self, hook_module, temp_config_dir):
        """Test that None is returned when GPU is disabled."""
        config_file = temp_config_dir / "config.ini"
        config_file.write_text(
            """
[General]
gpu_opt_in = false
gpu_pack_path = /path/to/gpu/pack
"""
        )

        result = hook_module.read_gpu_pack_path(config_file)
        assert result is None

    def test_no_gpu_pack_path(self, hook_module, temp_config_dir):
        """Test that None is returned when no gpu_pack_path is found."""
        config_file = temp_config_dir / "config.ini"
        config_file.write_text(
            """
[General]
gpu_opt_in = true
"""
        )

        # Auto-discovery disabled in non-frozen mode, so returns None
        result = hook_module.read_gpu_pack_path(config_file)
        assert result is None

    def test_empty_gpu_pack_path(self, hook_module, temp_config_dir):
        """Test that None is returned when gpu_pack_path is empty."""
        config_file = temp_config_dir / "config.ini"
        config_file.write_text(
            """
[General]
gpu_opt_in = true
gpu_pack_path =
"""
        )

        result = hook_module.read_gpu_pack_path(config_file)
        assert result is None

    def test_quoted_path(self, hook_module, temp_config_dir, tmp_path):
        """Test that quoted paths are handled correctly."""
        # Create actual GPU Pack directory
        gpu_pack = tmp_path / "gpu_pack_quoted"
        gpu_pack.mkdir()
        (gpu_pack / "torch").mkdir()

        config_file = temp_config_dir / "config.ini"
        config_file.write_text(
            f"""
[General]
gpu_pack_path = "{gpu_pack}"
"""
        )

        result = hook_module.read_gpu_pack_path(config_file)
        assert result == gpu_pack

    def test_file_read_error(self, hook_module, temp_config_dir):
        """Test that None is returned on file read error."""
        result = hook_module.read_gpu_pack_path(Path("/nonexistent/file.ini"))
        assert result is None


class TestAddDllDirectory:
    """Test add_dll_directory function."""

    def test_windows_add_dll_directory(self, hook_functions):
        """Test Windows DLL directory addition."""
        mock_add_dll = MagicMock()
        lib_dir = Path("C:\\gpu_pack\\torch\\lib")

        with patch("sys.platform", "win32"), patch("os.add_dll_directory", mock_add_dll):
            hook_functions["add_dll_directory"](lib_dir)
            mock_add_dll.assert_called_once_with(str(lib_dir))

    def test_windows_add_dll_directory_error(self, hook_functions):
        """Test that Windows DLL directory errors are handled silently."""
        lib_dir = Path("C:\\gpu_pack\\torch\\lib")

        with patch("sys.platform", "win32"), patch("os.add_dll_directory", side_effect=OSError("Permission denied")):
            # Should not raise
            hook_functions["add_dll_directory"](lib_dir)

    def test_linux_ld_library_path(self, hook_functions):
        """Test Linux LD_LIBRARY_PATH update."""
        lib_dir = Path("/opt/gpu_pack/torch/lib")

        with patch("sys.platform", "linux"), patch.dict("os.environ", {}, clear=True):
            hook_functions["add_dll_directory"](lib_dir)
            assert os.environ.get("LD_LIBRARY_PATH") == str(lib_dir)

    def test_linux_ld_library_path_append(self, hook_functions):
        """Test Linux LD_LIBRARY_PATH append to existing."""
        lib_dir = Path("/opt/gpu_pack/torch/lib")

        with patch("sys.platform", "linux"), patch.dict("os.environ", {"LD_LIBRARY_PATH": "/existing/path"}):
            hook_functions["add_dll_directory"](lib_dir)
            assert os.environ.get("LD_LIBRARY_PATH") == f"{lib_dir}:/existing/path"

    def test_macos_dyld_library_path(self, hook_functions):
        """Test macOS DYLD_LIBRARY_PATH update."""
        lib_dir = Path("/opt/gpu_pack/torch/lib")

        with patch("sys.platform", "darwin"), patch.dict("os.environ", {}, clear=True):
            hook_functions["add_dll_directory"](lib_dir)
            assert os.environ.get("DYLD_LIBRARY_PATH") == str(lib_dir)


class TestReorderSyspathForGpuPack:
    """Test reorder_syspath_for_gpu_pack function."""

    def test_adds_pack_to_start(self, hook_functions):
        """Test that GPU Pack is added to start of sys.path."""
        pack_dir = Path("/opt/gpu_pack")
        original_path = sys.path.copy()

        # Mock _MEIPASS
        sys._MEIPASS = "/tmp/_MEI12345"
        sys.path.append(sys._MEIPASS)

        try:
            hook_functions["reorder_syspath_for_gpu_pack"](pack_dir)
            assert sys.path[0] == str(pack_dir)
        finally:
            # Restore original sys.path
            sys.path[:] = original_path
            if hasattr(sys, "_MEIPASS"):
                delattr(sys, "_MEIPASS")

    def test_moves_meipass_to_end(self, hook_functions):
        """Test that _MEIPASS directory itself is moved to end (not derived paths)."""
        pack_dir = Path("/opt/gpu_pack")
        meipass = "/tmp/_MEI12345"

        # Setup: include both _MEIPASS and a derived path (like base_library.zip)
        sys._MEIPASS = meipass
        base_lib = meipass + "/base_library.zip"
        original_path = [base_lib, "/some/path", meipass, "/another/path"]
        sys.path[:] = original_path.copy()

        try:
            hook_functions["reorder_syspath_for_gpu_pack"](pack_dir)

            # GPU Pack should be first
            assert sys.path[0] == str(pack_dir)
            # _MEIPASS directory should be last
            assert sys.path[-1] == meipass
            # base_library.zip should still be in its original position (not moved)
            assert base_lib in sys.path
            # _MEIPASS should appear only once
            assert sys.path.count(meipass) == 1
        finally:
            sys.path[:] = original_path
            delattr(sys, "_MEIPASS")


class TestSetupGpuPack:
    """Test main setup_gpu_pack function."""

    def test_skips_when_not_frozen(self, hook_functions):
        """Test that setup is skipped when not frozen."""
        # Ensure _MEIPASS doesn't exist
        if hasattr(sys, "_MEIPASS"):
            delattr(sys, "_MEIPASS")

        original_path = sys.path.copy()
        hook_functions["setup_gpu_pack"]()

        # sys.path should be unchanged
        assert sys.path == original_path

    def test_skips_when_config_missing(self, hook_module, temp_config_dir):
        """Test that setup is skipped when config doesn't exist."""
        sys._MEIPASS = "/tmp/_MEI12345"
        original_path = sys.path.copy()

        try:
            with patch.object(hook_module, "get_config_dir", return_value=temp_config_dir):
                hook_module.setup_gpu_pack()

            # sys.path should be unchanged
            assert sys.path == original_path
        finally:
            delattr(sys, "_MEIPASS")

    def test_full_setup_success(self, hook_module, temp_config_dir, temp_gpu_pack):
        """Test successful full GPU Pack setup."""
        # Create ABI-compatible torch/_C file for current Python version
        py_version = f"cp{sys.version_info.major}{sys.version_info.minor}"
        torch_c = temp_gpu_pack / "torch" / f"_C.{py_version}-win_amd64.pyd"
        torch_c.touch()

        # Create config
        config_file = temp_config_dir / "config.ini"
        config_file.write_text(
            f"""
[General]
gpu_opt_in = true
gpu_pack_path = {temp_gpu_pack}
"""
        )

        sys._MEIPASS = "/tmp/_MEI12345"
        sys.path.append(sys._MEIPASS)
        original_path = sys.path.copy()
        original_meta_path = sys.meta_path.copy()

        try:
            with (
                patch("sys.platform", "win32"),
                patch.object(hook_module, "get_config_dir", return_value=temp_config_dir),
            ):
                hook_module.setup_gpu_pack()

            # GPU Pack should be first in sys.path
            assert sys.path[0] == str(temp_gpu_pack)
            # _MEIPASS should be at end
            assert sys.path[-1] == sys._MEIPASS
            # MetaPathFinder should be inserted at sys.meta_path[0]
            assert sys.meta_path[0].__class__.__name__ == "GPUPackImportFinder"
        finally:
            sys.path[:] = original_path
            sys.meta_path[:] = original_meta_path
            delattr(sys, "_MEIPASS")


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_malformed_config_file(self, hook_module, temp_config_dir):
        """Test that malformed config doesn't break setup."""
        config_file = temp_config_dir / "config.ini"
        config_file.write_bytes(b"\xff\xfe\x00invalid UTF-8")

        # Should not raise
        result = hook_module.read_gpu_pack_path(config_file)
        assert result is None

    def test_nonexistent_pack_directory(self, hook_module, temp_config_dir):
        """Test that nonexistent pack directory is handled."""
        config_file = temp_config_dir / "config.ini"
        config_file.write_text(
            """
[General]
gpu_opt_in = true
gpu_pack_path = /nonexistent/path
"""
        )

        sys._MEIPASS = "/tmp/_MEI12345"
        original_path = sys.path.copy()

        try:
            # Should not raise - mock get_config_dir to prevent auto-discovery
            with patch.object(hook_module, "get_config_dir", return_value=temp_config_dir):
                hook_module.setup_gpu_pack()

            # sys.path should be unchanged (except for _MEIPASS we added)
            assert len(sys.path) == len(original_path)
        finally:
            sys.path[:] = original_path
            delattr(sys, "_MEIPASS")

    def test_pack_missing_torch_subdirectory(self, hook_module, temp_config_dir, tmp_path):
        """Test that pack without torch/ subdirectory is handled."""
        pack_dir = tmp_path / "incomplete_pack"
        pack_dir.mkdir()

        config_file = temp_config_dir / "config.ini"
        config_file.write_text(
            f"""
[General]
gpu_opt_in = true
gpu_pack_path = {pack_dir}
"""
        )

        sys._MEIPASS = "/tmp/_MEI12345"
        original_path = sys.path.copy()

        try:
            with patch.object(hook_module, "get_config_dir", return_value=temp_config_dir):
                # Should not raise
                hook_module.setup_gpu_pack()

            # sys.path should be unchanged
            assert str(pack_dir) not in sys.path
        finally:
            sys.path[:] = original_path
            delattr(sys, "_MEIPASS")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
