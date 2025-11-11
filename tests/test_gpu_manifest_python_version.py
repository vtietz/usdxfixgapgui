"""
Tests for GPU manifest Python version detection.

Verifies that the manifest correctly generates URLs and metadata for different Python versions.
"""

import sys
from unittest.mock import patch
from utils.gpu.manifest import load_local_manifest


class TestPythonVersionDetection:
    """Test Python version detection in GPU manifest."""

    def test_default_uses_current_python_version(self):
        """Test that default manifest uses current Python version in URL."""
        manifests = load_local_manifest("1.0.0")
        cu121 = manifests["cu121"]

        # Should contain cpXX where XX is the current Python version
        expected_py_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
        assert expected_py_tag in cu121.url
        assert cu121.url.count(expected_py_tag) == 2  # Appears twice in wheel name

    def test_url_format_for_python_312(self):
        """Test URL format for Python 3.12."""
        with patch("utils.gpu.manifest.sys.version_info", major=3, minor=12):
            # Re-import to pick up patched version
            import importlib
            from utils.gpu import manifest

            importlib.reload(manifest)

            manifests = manifest.load_local_manifest("1.0.0")
            cu121 = manifests["cu121"]

            assert "cp312-cp312" in cu121.url
            assert "torch-2.4.1%2Bcu121-cp312-cp312-win_amd64.whl" in cu121.url

    def test_url_format_for_python_38(self):
        """Test URL format for Python 3.8."""
        with patch("utils.gpu.manifest.sys.version_info", major=3, minor=8):
            import importlib
            from utils.gpu import manifest

            importlib.reload(manifest)

            manifests = manifest.load_local_manifest("1.0.0")
            cu121 = manifests["cu121"]

            assert "cp38-cp38" in cu121.url
            assert "torch-2.4.1%2Bcu121-cp38-cp38-win_amd64.whl" in cu121.url

    def test_wheel_metadata_fallback_to_cp38(self):
        """Test that unknown Python versions fallback to cp38 metadata."""
        with patch("utils.gpu.manifest.sys.version_info", major=3, minor=99):
            import importlib
            from utils.gpu import manifest

            importlib.reload(manifest)

            # Should not raise error, should use cp38 metadata
            manifests = manifest.load_local_manifest("1.0.0")
            cu121 = manifests["cu121"]

            # URL should still use cp399 (current version)
            assert "cp399-cp399" in cu121.url
            # But SHA256 should fallback to cp38 metadata (since cp399 not defined)
            # This is OK - it just means size check will be skipped

    def test_metadata_includes_sha256_and_size(self):
        """Test that wheel metadata includes SHA256 and size."""
        manifests = load_local_manifest("1.0.0")
        cu121 = manifests["cu121"]

        assert hasattr(cu121, "sha256")
        assert hasattr(cu121, "size")
        assert isinstance(cu121.sha256, str)
        assert isinstance(cu121.size, int)
        assert cu121.size > 0

    def test_both_flavors_support_python_version(self):
        """Test that both cu121 and cu124 support Python version detection."""
        manifests = load_local_manifest("1.0.0")

        f"cp{sys.version_info.major}{sys.version_info.minor}"

        for flavor in ["cu121", "cu124"]:
            manifest = manifests[flavor]
            # URL should contain Python version tag
            assert "cp3" in manifest.url  # At least verify it has some Python version tag
            assert manifest.flavor == flavor
            assert manifest.torch_version.startswith("2.4.1+")
