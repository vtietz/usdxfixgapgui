#!/usr/bin/env python
"""Check CUDA availability for PyTorch."""

import torch

print("=" * 60)
print("PyTorch CUDA Configuration Check")
print("=" * 60)
print(f"PyTorch Version: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
print(f"CUDA Version: {torch.version.cuda if torch.cuda.is_available() else 'N/A'}")
print(f"cuDNN Version: {torch.backends.cudnn.version() if torch.cuda.is_available() else 'N/A'}")
print(f"Device Count: {torch.cuda.device_count()}")

if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        print(f"\nGPU {i}: {torch.cuda.get_device_name(i)}")
        print(f"  Compute Capability: {torch.cuda.get_device_capability(i)}")
        print(f"  Total Memory: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.2f} GB")
else:
    print("\n⚠️  CUDA is NOT available!")
    print("\nPossible reasons:")
    print("1. PyTorch CPU-only version is installed")
    print("2. NVIDIA GPU drivers not installed or outdated")
    print("3. CUDA toolkit not installed or incompatible")
    print("\nTo install PyTorch with CUDA support:")
    print("  Visit: https://pytorch.org/get-started/locally/")
    print("  Example: pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")

print("=" * 60)
