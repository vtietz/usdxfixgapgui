"""
MDX-Net Detection Provider Package

Modular implementation of MDX-Net based vocal separation and gap detection.
Decomposed from monolithic mdx_provider.py for maintainability and testability.
"""

from .config import MdxConfig
from .model_loader import ModelLoader
from .logging import flush_logs
from .separator import separate_vocals_chunk
from .detection import detect_onset_in_vocal_chunk, compute_rms, estimate_noise_floor

__all__ = [
    'MdxConfig',
    'ModelLoader', 
    'flush_logs',
    'separate_vocals_chunk',
    'detect_onset_in_vocal_chunk',
    'compute_rms',
    'estimate_noise_floor'
]
