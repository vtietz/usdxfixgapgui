"""
Configuration Validator

Validates configuration values at startup to prevent runtime errors.
Auto-fixes invalid configurations with warnings.
"""

import logging
import sys
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class ConfigValidationError:
    """Represents a configuration validation issue."""

    def __init__(self, key: str, current_value, recommended_value, reason: str, severity: str = "warning"):
        self.key = key
        self.current_value = current_value
        self.recommended_value = recommended_value
        self.reason = reason
        self.severity = severity  # "warning", "error", "info"

    def __str__(self):
        return (
            f"[{self.severity.upper()}] {self.key}={self.current_value} "
            f"(recommended: {self.recommended_value}) - {self.reason}"
        )


def validate_mdx_config(config) -> List[ConfigValidationError]:
    """
    Validate MDX detection configuration.

    Checks for:
    - FP16 compatibility issues
    - Invalid threshold ranges
    - Contradictory settings

    Args:
        config: Config object to validate

    Returns:
        List of ConfigValidationError objects (empty if all valid)
    """
    errors = []

    # Check FP16 - known to cause type mismatch with Demucs
    if hasattr(config, "mdx_use_fp16") and config.mdx_use_fp16:
        errors.append(
            ConfigValidationError(
                key="mdx.use_fp16",
                current_value=True,
                recommended_value=False,
                reason="FP16 causes type mismatch errors with Demucs (Half vs Float bias). "
                "Use TF32 for acceleration instead.",
                severity="error",
            )
        )

    # Check threshold ranges
    if hasattr(config, "mdx_onset_snr_threshold"):
        snr = config.mdx_onset_snr_threshold
        if snr < 3.0:
            errors.append(
                ConfigValidationError(
                    key="mdx.onset_snr_threshold",
                    current_value=snr,
                    recommended_value=6.5,
                    reason="SNR threshold too low - will detect excessive noise/false positives",
                    severity="warning",
                )
            )
        elif snr > 12.0:
            errors.append(
                ConfigValidationError(
                    key="mdx.onset_snr_threshold",
                    current_value=snr,
                    recommended_value=6.5,
                    reason="SNR threshold too high - will miss quiet vocal starts",
                    severity="warning",
                )
            )

    if hasattr(config, "mdx_onset_abs_threshold"):
        abs_thresh = config.mdx_onset_abs_threshold
        if abs_thresh < 0.005:
            errors.append(
                ConfigValidationError(
                    key="mdx.onset_abs_threshold",
                    current_value=abs_thresh,
                    recommended_value=0.020,
                    reason="Absolute threshold too low - will detect noise",
                    severity="warning",
                )
            )
        elif abs_thresh > 0.1:
            errors.append(
                ConfigValidationError(
                    key="mdx.onset_abs_threshold",
                    current_value=abs_thresh,
                    recommended_value=0.020,
                    reason="Absolute threshold too high - will miss quiet vocals",
                    severity="warning",
                )
            )

    # Check minimum duration
    if hasattr(config, "mdx_min_voiced_duration_ms"):
        min_dur = config.mdx_min_voiced_duration_ms
        if min_dur < 50:
            errors.append(
                ConfigValidationError(
                    key="mdx.min_voiced_duration_ms",
                    current_value=min_dur,
                    recommended_value=200,
                    reason="Minimum duration too short - will detect noise spikes",
                    severity="warning",
                )
            )
        elif min_dur > 1000:
            errors.append(
                ConfigValidationError(
                    key="mdx.min_voiced_duration_ms",
                    current_value=min_dur,
                    recommended_value=200,
                    reason="Minimum duration too long - will miss short vocal phrases",
                    severity="warning",
                )
            )

    # Check TF32 only used on CUDA, but avoid importing torch prematurely.
    # Only perform the check if torch is already imported by this point.
    if hasattr(config, "mdx_tf32") and config.mdx_tf32:
        try:
            if "torch" in sys.modules:
                import torch

                if not torch.cuda.is_available():
                    errors.append(
                        ConfigValidationError(
                            key="mdx.tf32",
                            current_value=True,
                            recommended_value=False,
                            reason="TF32 only works on CUDA - no GPU detected",
                            severity="info",
                        )
                    )
            # If torch is not yet imported, defer the check to avoid forcing CPU torch to load.
        except Exception:
            # Best-effort: don't block startup if any import/check fails here.
            pass

    return errors


def validate_config(config, auto_fix: bool = True) -> Tuple[bool, List[ConfigValidationError]]:
    """
    Validate configuration and optionally auto-fix errors.

    Args:
        config: Config object to validate
        auto_fix: If True, automatically fix critical errors

    Returns:
        Tuple of (is_valid, list_of_errors)
        is_valid is False only if there are unfixed errors
    """
    all_errors = []

    # Validate MDX config
    mdx_errors = validate_mdx_config(config)
    all_errors.extend(mdx_errors)

    # Auto-fix critical errors if requested
    fixed_any = False
    if auto_fix:
        for error in all_errors:
            if error.severity == "error":
                logger.warning(f"Auto-fixing config: {error}")

                # Apply fix
                if error.key == "mdx.use_fp16":
                    config.mdx_use_fp16 = False
                    config._config.set("mdx", "use_fp16", "false")
                    logger.info("✓ Disabled FP16 to prevent type mismatch errors")
                    fixed_any = True

        # Save fixes to config file
        if fixed_any:
            try:
                config.save()
                logger.info("✓ Auto-fixes saved to config file")

                # Re-validate to get fresh error list after fixes
                all_errors = []
                mdx_errors = validate_mdx_config(config)
                all_errors.extend(mdx_errors)
            except Exception as e:
                logger.error(f"Failed to save auto-fixes: {e}")

    # Check if any unfixed errors remain
    remaining_errors = [e for e in all_errors if e.severity == "error"]
    is_valid = len(remaining_errors) == 0

    # Log warnings
    warnings = [e for e in all_errors if e.severity == "warning"]
    if warnings:
        logger.info(f"Configuration has {len(warnings)} warning(s):")
        for warning in warnings:
            logger.warning(f"  {warning}")

    return is_valid, all_errors


def print_validation_report(errors: List[Dict[str, Any]]):
    """
    Print a user-friendly validation report grouped by severity.

    Args:
        errors: List of validation errors with severity, field, and message
    """
    if not errors:
        return

    # Group errors by severity
    errors_by_severity = {"error": [], "warning": [], "info": []}
    for error in errors:
        # ConfigValidationError is an object, not a dict
        severity = getattr(error, "severity", "warning")
        key = getattr(error, "key", "unknown")
        reason = getattr(error, "reason", "")
        current = getattr(error, "current_value", "")
        recommended = getattr(error, "recommended_value", "")

        # Format message with key, current value, and reason
        if recommended:
            msg = f"{key}={current} (recommended: {recommended}) - {reason}"
        else:
            msg = f"{key}={current} - {reason}"

        errors_by_severity[severity].append(msg)

    # Use ASCII-safe symbols for console compatibility (Windows cp1252)
    # Emoji can't be encoded in cp1252 which is the default console encoding
    try:
        print()
        print("=" * 70)
        print("CONFIGURATION VALIDATION REPORT")
        print("=" * 70)

        if errors_by_severity["error"]:
            print(f"\nX ERRORS ({len(errors_by_severity['error'])}):")
            for error in errors_by_severity["error"]:
                # Use safe printing to handle unicode characters
                safe_error = error.encode('ascii', 'replace').decode('ascii')
                print(f"  - [ERROR] {safe_error}")

        if errors_by_severity["warning"]:
            print(f"\n! WARNINGS ({len(errors_by_severity['warning'])}):")
            for warning in errors_by_severity["warning"]:
                safe_warning = warning.encode('ascii', 'replace').decode('ascii')
                print(f"  - [WARNING] {safe_warning}")

        if errors_by_severity["info"]:
            print(f"\ni INFO ({len(errors_by_severity['info'])}):")
            for info in errors_by_severity["info"]:
                safe_info = info.encode('ascii', 'replace').decode('ascii')
                print(f"  - [INFO] {safe_info}")

        print("\nSee docs/mdx-detection-tuning.md for parameter guidance")
        print("=" * 70 + "\n")
    except Exception as e:
        # Fallback: if printing fails, write to stderr and log debug details
        import sys
        logger.debug(f"Failed to render validation report: {e}")
        sys.stderr.write(
            f"Configuration validation completed with {len(errors)} issue(s). Check log file for details.\n"
        )
