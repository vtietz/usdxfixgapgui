"""
MDX-Net Detection Provider Package

Modular implementation of MDX-Net based vocal separation and gap detection.
Decomposed from monolithic mdx_provider.py for maintainability and testability.

NOTE: Imports are lazy to prevent importing torch during initial config loading.
Config loading happens before GPU bootstrap, so we must defer torch imports.
"""

def __getattr__(name):
    """Lazy imports to avoid loading torch before GPU bootstrap."""
    if name == "MdxConfig":
        from .config import MdxConfig
        return MdxConfig
    elif name == "ModelLoader":
        from .model_loader import ModelLoader
        return ModelLoader
    elif name == "flush_logs":
        from .logging import flush_logs
        return flush_logs
    elif name == "separate_vocals_chunk":
        from .separator import separate_vocals_chunk
        return separate_vocals_chunk
    elif name == "detect_onset_in_vocal_chunk":
        from .detection import detect_onset_in_vocal_chunk
        return detect_onset_in_vocal_chunk
    elif name == "compute_rms":
        from .detection import compute_rms
        return compute_rms
    elif name == "estimate_noise_floor":
        from .detection import estimate_noise_floor
        return estimate_noise_floor
    elif name == "compute_confidence_score":
        from .confidence import compute_confidence_score
        return compute_confidence_score
    elif name == "VocalsCache":
        from .vocals_cache import VocalsCache
        return VocalsCache
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "MdxConfig",
    "ModelLoader",
    "flush_logs",
    "separate_vocals_chunk",
    "detect_onset_in_vocal_chunk",
    "compute_rms",
    "estimate_noise_floor",
    "compute_confidence_score",
    "VocalsCache",
]
