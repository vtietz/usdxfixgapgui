"""Test that config uses relative paths in portable mode."""

import os
import tempfile
from unittest import mock

from common.config import Config


class TestPortableModePathConversion:
    """Test portable mode path handling."""

    def test_make_path_portable_converts_to_relative_in_portable_mode(self):
        """In portable mode, paths under app_dir should be converted to relative."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create config in temp dir
            config_path = os.path.join(tmp_dir, "config.ini")

            # Mock portable mode
            app_dir = tmp_dir
            with (
                mock.patch("common.config.is_portable_mode", return_value=True),
                mock.patch("common.config.get_app_dir", return_value=app_dir),
            ):

                config = Config(custom_config_path=config_path)

                # Test path under app_dir → should become relative
                models_path = os.path.join(app_dir, "models", "pretrained")
                result = config._make_path_portable(models_path)

                # Should be relative
                assert result.startswith("./")
                assert "models" in result
                assert "pretrained" in result

    def test_make_path_portable_keeps_absolute_when_not_portable(self):
        """In non-portable mode, paths should remain absolute."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.ini")

            # Mock non-portable mode
            with mock.patch("common.config.is_portable_mode", return_value=False):
                config = Config(custom_config_path=config_path)

                test_path = "C:\\Users\\test\\models"
                result = config._make_path_portable(test_path)

                # Should remain absolute
                assert result == test_path

    def test_make_path_portable_keeps_absolute_when_outside_app_dir(self):
        """Paths outside app_dir should remain absolute even in portable mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.ini")

            # Mock portable mode with app_dir
            app_dir = tmp_dir
            with (
                mock.patch("common.config.is_portable_mode", return_value=True),
                mock.patch("common.config.get_app_dir", return_value=app_dir),
            ):

                config = Config(custom_config_path=config_path)

                # Path outside app_dir
                external_path = "C:\\Program Files\\SomeApp\\models"
                result = config._make_path_portable(external_path)

                # Should remain absolute (not under app_dir)
                assert not result.startswith("./")

    def test_resolve_path_from_config_resolves_relative_in_portable_mode(self):
        """Relative paths from config should be resolved to absolute in portable mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.ini")

            # Mock portable mode
            app_dir = tmp_dir
            with (
                mock.patch("common.config.is_portable_mode", return_value=True),
                mock.patch("common.config.get_app_dir", return_value=app_dir),
            ):

                config = Config(custom_config_path=config_path)

                # Test resolving relative path
                relative_path = "./models/pretrained"
                result = config._resolve_path_from_config(relative_path)

                # Should be absolute
                assert os.path.isabs(result)
                assert result.startswith(app_dir)
                assert "models" in result

    def test_resolve_path_from_config_keeps_absolute_when_not_relative(self):
        """Absolute paths from config should remain unchanged."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.ini")

            with mock.patch("common.config.is_portable_mode", return_value=True):
                config = Config(custom_config_path=config_path)

                absolute_path = "C:\\Users\\test\\models"
                result = config._resolve_path_from_config(absolute_path)

                # Should remain unchanged
                assert result == absolute_path

    def test_save_and_load_round_trip_in_portable_mode(self):
        """Save with relative paths, load should resolve back to absolute."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.ini")

            # Mock portable mode
            app_dir = tmp_dir
            with (
                mock.patch("common.config.is_portable_mode", return_value=True),
                mock.patch("common.config.get_app_dir", return_value=app_dir),
                mock.patch("common.config.get_localappdata_dir", return_value=app_dir),
            ):

                # Create config and set paths
                config = Config(custom_config_path=config_path)

                # Set paths under app_dir
                models_path = os.path.join(app_dir, "models")
                gpu_path = os.path.join(app_dir, "gpu_pack")
                tmp_path = os.path.join(app_dir, ".tmp")
                samples_path = os.path.join(app_dir, "samples")

                config.last_directory = models_path
                config.gpu_pack_path = gpu_path
                config.tmp_root = tmp_path
                config.default_directory = samples_path
                config.save()

                # Verify paths were saved as relative in config file
                import configparser

                saved_config = configparser.ConfigParser()
                saved_config.read(config_path)

                saved_last_dir = saved_config.get("Paths", "last_directory")
                saved_gpu_path = saved_config.get("General", "gpu_pack_path")
                saved_tmp_root = saved_config.get("Paths", "tmp_root")
                saved_default_dir = saved_config.get("Paths", "default_directory")

                # last_directory stays absolute (user's external folders)
                assert os.path.isabs(saved_last_dir) or saved_last_dir == ""

                # App-internal paths should be relative
                assert saved_gpu_path.startswith("./")
                assert saved_tmp_root.startswith("./")
                assert saved_default_dir.startswith("./")

                # Load config again - paths should be resolved to absolute
                config2 = Config(custom_config_path=config_path)

                # Should be absolute
                assert os.path.isabs(config2.tmp_root)
                assert os.path.isabs(config2.default_directory)
                assert os.path.isabs(config2.gpu_pack_path)

                # Should match original absolute paths
                assert config2.tmp_root == tmp_path
                assert config2.default_directory == samples_path
                assert config2.gpu_pack_path == gpu_path

    def test_empty_paths_handled_correctly(self):
        """Empty paths should remain empty."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.ini")

            with mock.patch("common.config.is_portable_mode", return_value=True):
                config = Config(custom_config_path=config_path)

                # Empty path
                assert config._make_path_portable("") == ""
                assert config._resolve_path_from_config("") == ""

    def test_defaults_use_relative_paths_in_portable_mode(self):
        """Default paths should be relative in portable mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.ini")

            # Mock portable mode
            app_dir = tmp_dir
            with (
                mock.patch("common.config.is_portable_mode", return_value=True),
                mock.patch("common.config.get_app_dir", return_value=app_dir),
                mock.patch("common.config.get_localappdata_dir", return_value=app_dir),
            ):

                # Create config - should get relative defaults
                config = Config(custom_config_path=config_path)

                # tmp_root and default_directory should be resolved to absolute at runtime
                assert os.path.isabs(config.tmp_root)
                assert os.path.isabs(config.default_directory)

                # Save config
                config.save()

                # Check saved values are relative
                import configparser

                saved_config = configparser.ConfigParser()
                saved_config.read(config_path)

                saved_tmp = saved_config.get("Paths", "tmp_root")
                saved_default = saved_config.get("Paths", "default_directory")

                # Should be relative in config file
                assert saved_tmp.startswith("./")
                assert saved_default.startswith("./")

    def test_defaults_use_absolute_paths_in_nonportable_mode(self):
        """Default paths should be absolute in non-portable mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "config.ini")

            with mock.patch("common.config.is_portable_mode", return_value=False):
                # Create config - should get absolute defaults
                config = Config(custom_config_path=config_path)

                # tmp_root and default_directory should be absolute
                assert os.path.isabs(config.tmp_root)
                assert os.path.isabs(config.default_directory)

                # Save config
                config.save()

                # Check saved values are absolute
                import configparser

                saved_config = configparser.ConfigParser()
                saved_config.read(config_path)

                saved_tmp = saved_config.get("Paths", "tmp_root")
                saved_default = saved_config.get("Paths", "default_directory")

                # Should be absolute in config file
                assert os.path.isabs(saved_tmp)
                assert os.path.isabs(saved_default)
