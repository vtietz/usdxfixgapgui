"""
Tests for configuration validator.

Ensures invalid configurations are detected and can be auto-fixed.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from utils.config_validator import (
    validate_mdx_config,
    validate_config,
    ConfigValidationError
)


class TestMdxConfigValidation:
    """Test MDX configuration validation."""

    def test_fp16_detected_as_error(self):
        """FP16 enabled should be detected as error."""
        config = Mock()
        config.mdx_use_fp16 = True
        config.mdx_onset_snr_threshold = 6.5
        config.mdx_onset_abs_threshold = 0.020
        config.mdx_min_voiced_duration_ms = 200
        config.mdx_tf32 = False

        errors = validate_mdx_config(config)

        # Should have FP16 error
        fp16_errors = [e for e in errors if e.key == "mdx.use_fp16"]
        assert len(fp16_errors) == 1
        assert fp16_errors[0].severity == "error"
        assert fp16_errors[0].recommended_value is False

    def test_fp16_disabled_no_error(self):
        """FP16 disabled should pass validation."""
        config = Mock()
        config.mdx_use_fp16 = False
        config.mdx_onset_snr_threshold = 6.5
        config.mdx_onset_abs_threshold = 0.020
        config.mdx_min_voiced_duration_ms = 200
        config.mdx_tf32 = True

        errors = validate_mdx_config(config)

        # Should have no FP16 errors
        fp16_errors = [e for e in errors if e.key == "mdx.use_fp16"]
        assert len(fp16_errors) == 0

    def test_snr_threshold_too_low_warning(self):
        """SNR threshold < 3.0 should trigger warning."""
        config = Mock()
        config.mdx_use_fp16 = False
        config.mdx_onset_snr_threshold = 2.0  # Too low
        config.mdx_onset_abs_threshold = 0.020
        config.mdx_min_voiced_duration_ms = 200

        errors = validate_mdx_config(config)

        snr_warnings = [e for e in errors if e.key == "mdx.onset_snr_threshold"]
        assert len(snr_warnings) == 1
        assert snr_warnings[0].severity == "warning"

    def test_snr_threshold_too_high_warning(self):
        """SNR threshold > 12.0 should trigger warning."""
        config = Mock()
        config.mdx_use_fp16 = False
        config.mdx_onset_snr_threshold = 15.0  # Too high
        config.mdx_onset_abs_threshold = 0.020
        config.mdx_min_voiced_duration_ms = 200

        errors = validate_mdx_config(config)

        snr_warnings = [e for e in errors if e.key == "mdx.onset_snr_threshold"]
        assert len(snr_warnings) == 1
        assert snr_warnings[0].severity == "warning"

    def test_abs_threshold_too_low_warning(self):
        """Absolute threshold < 0.005 should trigger warning."""
        config = Mock()
        config.mdx_use_fp16 = False
        config.mdx_onset_snr_threshold = 6.5
        config.mdx_onset_abs_threshold = 0.001  # Too low
        config.mdx_min_voiced_duration_ms = 200

        errors = validate_mdx_config(config)

        abs_warnings = [e for e in errors if e.key == "mdx.onset_abs_threshold"]
        assert len(abs_warnings) == 1
        assert abs_warnings[0].severity == "warning"

    def test_valid_config_no_errors(self):
        """Valid configuration should pass with no errors."""
        config = Mock()
        config.mdx_use_fp16 = False
        config.mdx_onset_snr_threshold = 6.5
        config.mdx_onset_abs_threshold = 0.020
        config.mdx_min_voiced_duration_ms = 200
        config.mdx_tf32 = True

        errors = validate_mdx_config(config)

        # Should have no errors or warnings
        critical = [e for e in errors if e.severity in ["error", "warning"]]
        assert len(critical) == 0


class TestConfigAutoFix:
    """Test configuration auto-fix functionality."""

    def test_fp16_auto_fixed(self):
        """FP16 error should be auto-fixed."""
        config = Mock()
        config.mdx_use_fp16 = True
        config.mdx_onset_snr_threshold = 6.5
        config.mdx_onset_abs_threshold = 0.020
        config.mdx_min_voiced_duration_ms = 200
        config._config = Mock()
        config.save = Mock()

        is_valid, errors = validate_config(config, auto_fix=True)

        # Should be valid after auto-fix
        assert is_valid is True

        # Should have set FP16 to False
        assert config.mdx_use_fp16 is False
        config._config.set.assert_called_with('mdx', 'use_fp16', 'false')

        # Should have saved config
        config.save.assert_called_once()

    def test_warnings_not_auto_fixed(self):
        """Warnings should not be auto-fixed, only reported."""
        config = Mock()
        config.mdx_use_fp16 = False
        config.mdx_onset_snr_threshold = 2.0  # Warning: too low
        config.mdx_onset_abs_threshold = 0.020
        config.mdx_min_voiced_duration_ms = 200
        config._config = Mock()
        config.save = Mock()

        is_valid, errors = validate_config(config, auto_fix=True)

        # Should still be valid (warnings don't block)
        assert is_valid is True

        # Should have warnings
        warnings = [e for e in errors if e.severity == "warning"]
        assert len(warnings) > 0

        # Should NOT have changed config
        assert config.mdx_onset_snr_threshold == 2.0

        # Should NOT have saved (no fixes applied)
        config.save.assert_not_called()

    def test_auto_fix_disabled(self):
        """Auto-fix can be disabled."""
        config = Mock()
        config.mdx_use_fp16 = True
        config.mdx_onset_snr_threshold = 6.5
        config.mdx_onset_abs_threshold = 0.020
        config.mdx_min_voiced_duration_ms = 200
        config._config = Mock()
        config.save = Mock()

        is_valid, errors = validate_config(config, auto_fix=False)

        # Should NOT be valid (error not fixed)
        assert is_valid is False

        # Should NOT have changed config
        assert config.mdx_use_fp16 is True

        # Should NOT have saved
        config.save.assert_not_called()


class TestConfigValidationError:
    """Test ConfigValidationError class."""

    def test_error_string_representation(self):
        """Error should have readable string representation."""
        error = ConfigValidationError(
            key="test.key",
            current_value=True,
            recommended_value=False,
            reason="Test reason",
            severity="error"
        )

        error_str = str(error)
        assert "ERROR" in error_str
        assert "test.key" in error_str
        assert "True" in error_str
        assert "False" in error_str
        assert "Test reason" in error_str