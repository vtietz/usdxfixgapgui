"""
Model loading and caching for MDX detection.

Provides thread-safe model loading with instance-level caching to avoid
global mutable state. Handles device selection (CUDA/CPU) and optimizations
(FP16, cuDNN, threading).
"""

import logging
import threading

from utils.logging_utils import flush_logs

logger = logging.getLogger(__name__)

# Demucs model name - must be compatible with demucs.pretrained.get_model()
DEMUCS_MODEL_NAME = 'htdemucs'


class ModelLoader:
    """
    Thread-safe model loader with instance-level cache.

    Replaces global _GLOBAL_MODEL_CACHE to eliminate shared mutable state.
    Each instance maintains its own cache and lock.
    """

    def __init__(self):
        """Initialize empty cache and lock."""
        self._cache: dict = {'model': None, 'device': None}
        self._lock = threading.Lock()

    def get_device(self) -> str:
        """
        Determine optimal device for model execution.

        Returns:
            'cuda' if NVIDIA GPU available, otherwise 'cpu'
        """
        # Lazy import to avoid loading torch until needed
        import torch
        return 'cuda' if torch.cuda.is_available() else 'cpu'

    def get_model(self, device: str, use_fp16: bool):
        """
        Load Demucs model with GPU optimizations (thread-safe).

        Uses instance cache to avoid reloading model for each detection.
        Applies device-specific optimizations (cuDNN for GPU, threading for CPU).

        Args:
            device: Target device ('cuda' or 'cpu')
            use_fp16: Enable FP16 mixed precision (CUDA only)

        Returns:
            Loaded Demucs model in eval mode

        Raises:
            DetectionFailedError: If model loading fails
        """
        with self._lock:
            # Check if we can reuse cached model
            if self._cache['model'] is not None and self._cache['device'] == device:
                logger.info(f"Reusing cached Demucs model (device={device})")
                flush_logs()
                return self._cache['model']

            # Need to load model
            try:
                # Lazy imports - only load torch/demucs when actually needed
                import torch
                from demucs.pretrained import get_model
                from demucs.apply import apply_model
                from utils.providers.exceptions import DetectionFailedError

                device_name = "GPU (CUDA)" if device == 'cuda' else "CPU"
                logger.info(f"Loading Demucs model on {device_name}...")
                flush_logs()

                # Enable device-specific optimizations
                if device == 'cuda':
                    # Enable cuDNN auto-tuner for optimal convolution algorithms
                    torch.backends.cudnn.benchmark = True
                    logger.debug("Enabled cuDNN benchmark for GPU optimization")
                    flush_logs()

                    # Enable TF32 for faster matrix multiplication on Ampere+ GPUs
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
                    torch.set_float32_matmul_precision('high')
                    logger.debug("Enabled TF32 for faster matrix operations on CUDA")
                    flush_logs()
                else:
                    # CPU optimization: use most cores but leave one free
                    import os
                    cpu_count = os.cpu_count()
                    num_threads = max(1, cpu_count - 1) if cpu_count else 1
                    torch.set_num_threads(num_threads)
                    logger.debug(f"Set torch threads to {num_threads} for CPU optimization")
                    flush_logs()

                model = get_model(DEMUCS_MODEL_NAME)
                model.to(device)
                model.eval()

                # Cache in instance (not global)
                self._cache['model'] = model
                self._cache['device'] = device

                logger.info("Demucs model loaded successfully")
                flush_logs()

                # Warm up model with dummy input to trigger JIT compilation
                logger.info("Warming up model (JIT compilation, memory allocation)...")
                flush_logs()
                try:
                    dummy_input = torch.zeros(1, 2, 44100, device=device)  # 1 second stereo (already [1, 2, 44100])
                    with torch.no_grad():
                        if device == 'cuda' and use_fp16:
                            dummy_input = dummy_input.half()
                        # Use apply_model for Demucs inference (no additional unsqueeze needed)
                        _ = apply_model(model, dummy_input, device=device)
                    logger.info("Model warm-up complete, ready for detection")
                    flush_logs()
                except Exception as e:
                    logger.warning(f"Model warm-up failed (non-critical): {e}")
                    flush_logs()

                return model
            except Exception as e:
                # Import here to avoid circular dependency
                from utils.providers.exceptions import DetectionFailedError
                raise DetectionFailedError(
                    f"Failed to load Demucs model: {e}",
                    provider_name="mdx",
                    cause=e
                )
