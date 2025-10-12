@echo off
REM Uninstall CUDA-enabled PyTorch packages from conda environment
echo Uninstalling CUDA-enabled PyTorch packages...
echo.

REM Activate conda environment
call conda activate usdxfixgapgui

REM Uninstall CUDA PyTorch packages
echo Uninstalling torch, torchaudio, torchvision...
pip uninstall -y torch torchaudio torchvision

echo.
echo CUDA packages uninstalled successfully!
echo.
echo To install CPU-only versions, choose one:
echo.
echo Option 1 - CPU-only PyTorch (keeps Demucs support):
echo   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
echo.
echo Option 2 - Remove PyTorch entirely (Spleeter only):
echo   pip uninstall -y demucs
echo   (No reinstall needed - TensorFlow already installed)
echo.
pause
