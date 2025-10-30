"""
Tests for portable mode detection and data directory handling.
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from utils.files import is_portable_mode, get_localappdata_dir, get_app_dir


class TestPortableModeDetection:
    """Test portable mode detection logic."""

    def test_not_frozen_returns_false(self):
        """Non-frozen (script) mode should never be portable."""
        with patch.object(sys, 'frozen', False, create=True):
            assert is_portable_mode() is False

    def test_frozen_without_internal_dir_returns_false(self):
        """One-file exe (no _internal dir) is not portable mode."""
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, 'executable', '/tmp/usdxfixgap.exe'), \
             patch('os.path.isdir', return_value=False):
            assert is_portable_mode() is False

    def test_frozen_with_internal_dir_returns_true(self):
        """Directory build (with _internal) is portable mode."""
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, 'executable', '/tmp/usdxfixgap/usdxfixgap.exe'), \
             patch('os.path.isdir', return_value=True) as mock_isdir:
            result = is_portable_mode()
            assert result is True
            # Verify it checked for _internal directory
            mock_isdir.assert_called_once()
            call_path = mock_isdir.call_args[0][0]
            assert call_path.endswith('_internal')


class TestDataDirectorySelection:
    """Test that data directory respects portable mode."""

    def test_portable_mode_uses_app_dir(self):
        """Portable mode should store data alongside exe."""
        with patch('utils.files.is_portable_mode', return_value=True), \
             patch('utils.files.get_app_dir', return_value='/opt/usdxfixgap'):
            data_dir = get_localappdata_dir()
            assert data_dir == '/opt/usdxfixgap'

    @patch('sys.platform', 'win32')
    def test_windows_non_portable_uses_localappdata(self):
        """Windows non-portable should use LOCALAPPDATA."""
        with patch('utils.files.is_portable_mode', return_value=False), \
             patch.dict(os.environ, {'LOCALAPPDATA': r'C:\Users\Test\AppData\Local'}), \
             patch('os.makedirs'):
            data_dir = get_localappdata_dir()
            assert data_dir == r'C:\Users\Test\AppData\Local\USDXFixGap'

    @patch('sys.platform', 'darwin')
    def test_macos_non_portable_uses_app_support(self):
        """macOS non-portable should use Application Support."""
        with patch('utils.files.is_portable_mode', return_value=False), \
             patch('os.path.expanduser', return_value='/Users/test/Library/Application Support/USDXFixGap'), \
             patch('os.makedirs'):
            data_dir = get_localappdata_dir()
            assert 'Application Support' in data_dir

    @patch('sys.platform', 'linux')
    def test_linux_non_portable_uses_xdg(self):
        """Linux non-portable should use XDG directories."""
        with patch('utils.files.is_portable_mode', return_value=False), \
             patch('os.path.expanduser', return_value='/home/test/.local/share/USDXFixGap'), \
             patch('os.makedirs'):
            data_dir = get_localappdata_dir()
            assert '.local/share' in data_dir or 'XDG' in str(data_dir).upper()


class TestPortableModeIntegration:
    """Integration tests for portable mode data isolation."""

    def test_portable_mode_keeps_all_data_together(self):
        """In portable mode, config, cache, and models should be in same root."""
        from utils.files import get_models_dir

        with patch('utils.files.is_portable_mode', return_value=True), \
             patch('utils.files.get_app_dir', return_value='/portable/usdxfixgap'), \
             patch('os.makedirs'):
            
            data_dir = get_localappdata_dir()
            models_dir = get_models_dir()
            
            # Both should be under /portable/usdxfixgap
            assert data_dir == '/portable/usdxfixgap'
            assert models_dir.startswith('/portable/usdxfixgap')

    def test_one_file_mode_uses_system_directories(self):
        """One-file exe should use system directories, not temp extraction path."""
        from utils.files import get_models_dir

        with patch('utils.files.is_portable_mode', return_value=False), \
             patch('sys.platform', 'win32'), \
             patch.dict(os.environ, {'LOCALAPPDATA': r'C:\Users\Test\AppData\Local'}), \
             patch('os.makedirs'):
            
            data_dir = get_localappdata_dir()
            models_dir = get_models_dir()
            
            # Should use LOCALAPPDATA, not exe directory
            assert 'AppData' in data_dir
            assert 'AppData' in models_dir
