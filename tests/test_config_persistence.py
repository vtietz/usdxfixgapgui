"""Tests for Config persistence behavior.

Verifies that:
1. Config.save() preserves unrelated sections/keys
2. Backup files are created on save
3. Tests are isolated by default (don't touch real config)
4. Opt-in real config usage works with --config flag
"""

import os
import pytest
import tempfile
import configparser
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QObject

from src.common.config import Config
from src.utils.files import get_localappdata_dir


def create_test_config(config_path: str) -> Config:
    """Helper to create a Config instance with a custom path.
    
    Bypasses normal __init__ to allow testing with temp config files.
    """
    # Use Config's __new__ (from QObject) instead of object.__new__
    config = Config.__new__(Config)
    QObject.__init__(config)
    
    config.config_path = config_path
    config._config = configparser.ConfigParser()
    
    if os.path.exists(config_path):
        config._config.read(config_path, encoding='utf-8-sig')
    
    # Initialize properties with defaults
    config._initialize_properties()
    
    return config


class TestConfigPersistence:
    """Test that Config.save() preserves unrelated data."""

    def test_save_preserves_unrelated_sections(self):
        """Verify that saving config preserves sections/keys we don't manage."""
        # Create a temp config file with custom sections
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            config_path = f.name
            f.write("""[Paths]
last_directory = /original/path

[CustomSection]
custom_key = custom_value
another_key = 12345

[AnotherSection]
foo = bar
""")

        try:
            # Load config from our temp file
            config = create_test_config(config_path)
            
            # Modify last_directory
            config.last_directory = '/new/path'
            config.save()
            
            # Re-read the file directly
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding='utf-8-sig')
            
            # Verify our managed key was updated
            assert parser.get('Paths', 'last_directory') == '/new/path'
            
            # Verify unrelated sections/keys were preserved
            assert parser.has_section('CustomSection')
            assert parser.get('CustomSection', 'custom_key') == 'custom_value'
            assert parser.get('CustomSection', 'another_key') == '12345'
            
            assert parser.has_section('AnotherSection')
            assert parser.get('AnotherSection', 'foo') == 'bar'
            
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)
            backup_path = config_path + '.bak'
            if os.path.exists(backup_path):
                os.unlink(backup_path)

    def test_creates_backup_on_save(self):
        """Verify that save() creates a .bak backup file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            config_path = f.name
            f.write("""[Paths]
last_directory = /backup/test
""")

        try:
            config = create_test_config(config_path)
            
            # First save should create backup
            config.last_directory = '/new/path'
            config.save()
            
            backup_path = config_path + '.bak'
            assert os.path.exists(backup_path), "Backup file should be created"
            
            # Verify backup contains original content
            parser = configparser.ConfigParser()
            parser.read(backup_path, encoding='utf-8-sig')
            assert parser.get('Paths', 'last_directory') == '/backup/test'
            
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)
            backup_path = config_path + '.bak'
            if os.path.exists(backup_path):
                os.unlink(backup_path)

    def test_save_preserves_comments_workaround(self):
        """ConfigParser doesn't preserve comments, but verify sections/keys survive."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            config_path = f.name
            f.write("""# This is a comment that will be lost (known ConfigParser limitation)
[Paths]
last_directory = /test

[MySection]
# Another comment
my_key = my_value
""")

        try:
            config = create_test_config(config_path)
            config.last_directory = '/updated'
            config.save()
            
            # Re-read
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding='utf-8-sig')
            
            # Comments will be lost (ConfigParser limitation), but sections/keys survive
            assert parser.has_section('MySection')
            assert parser.get('MySection', 'my_key') == 'my_value'
            
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)
            backup_path = config_path + '.bak'
            if os.path.exists(backup_path):
                os.unlink(backup_path)


class TestTestIsolation:
    """Test that test isolation works correctly."""

    def test_default_tests_are_isolated(self):
        """Verify that by default, tests use isolated data directory."""
        # This test runs with the autouse fixture, so it should be isolated
        data_dir = get_localappdata_dir()
        
        # Should be a temp directory, not the real AppData location
        assert 'tmp' in data_dir.lower() or 'temp' in data_dir.lower(), \
            f"Expected isolated temp directory, got: {data_dir}"

    def test_isolated_config_independent_from_real_config(self):
        """Verify isolated config doesn't interfere with real user config."""
        # Get the isolated config location
        isolated_data_dir = get_localappdata_dir()
        config = Config()  # Uses isolated location
        
        # Modify it
        config.last_directory = '/isolated/test/path'
        config.save()
        
        # Verify the isolated config was written
        isolated_config_path = os.path.join(isolated_data_dir, 'config.ini')
        assert os.path.exists(isolated_config_path)
        
        parser = configparser.ConfigParser()
        parser.read(isolated_config_path, encoding='utf-8-sig')
        assert parser.get('Paths', 'last_directory') == '/isolated/test/path'
        
        # NOTE: We can't easily test that the REAL config is untouched without
        # disabling isolation, which would defeat the purpose. The isolation
        # fixture ensures real config is never touched.

    @pytest.mark.skipif(
        os.getenv('GAP_TEST_USE_CONFIG_INI') != '1',
        reason="This test requires GAP_TEST_USE_CONFIG_INI=1 to test real config access"
    )
    def test_opt_in_real_config(self):
        """When GAP_TEST_USE_CONFIG_INI=1, should use real config location.
        
        This test is SKIPPED by default. To run it:
        .\run.bat test --config tests/test_config_persistence.py::TestTestIsolation::test_opt_in_real_config
        """
        # This test should only run when explicitly opted in
        data_dir = get_localappdata_dir()
        
        # Should be real AppData, not temp
        assert 'tmp' not in data_dir.lower() and 'temp' not in data_dir.lower(), \
            f"With opt-in, expected real AppData, got: {data_dir}"
        
        # Verify config can be loaded from real location
        config = Config()
        assert config.config_path is not None


class TestConfigSaveEdgeCases:
    """Test edge cases in Config.save()."""

    def test_save_with_empty_last_directory(self):
        """Verify saving with empty last_directory works."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            config_path = f.name
            f.write("""[Paths]
last_directory = /old/path
""")

        try:
            config = create_test_config(config_path)
            config.last_directory = ''
            config.save()
            
            # Re-read
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding='utf-8-sig')
            assert parser.get('Paths', 'last_directory') == ''
            
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)
            backup_path = config_path + '.bak'
            if os.path.exists(backup_path):
                os.unlink(backup_path)

    def test_save_creates_missing_sections(self):
        """Verify save() creates missing sections if needed."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            config_path = f.name
            # Empty file
            f.write("")

        try:
            config = create_test_config(config_path)
            config.last_directory = '/new/path'
            config.save()
            
            # Re-read
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding='utf-8-sig')
            
            # Should have created Paths section
            assert parser.has_section('Paths')
            assert parser.get('Paths', 'last_directory') == '/new/path'
            
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)
            backup_path = config_path + '.bak'
            if os.path.exists(backup_path):
                os.unlink(backup_path)

    def test_save_handles_nonexistent_file(self):
        """Verify save() works even if file doesn't exist yet."""
        # Create a temp directory but no file
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'nonexistent.ini')
            
            config = create_test_config(config_path)
            config.last_directory = '/test/path'
            config.save()
            
            # File should now exist
            assert os.path.exists(config_path)
            
            # Verify content
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding='utf-8-sig')
            assert parser.get('Paths', 'last_directory') == '/test/path'
