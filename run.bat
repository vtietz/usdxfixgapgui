@echo off
setlocal EnableDelayedExpansion

:: Configuration
set ENV_NAME=usdxfixgapgui
set PYTHON_VERSION=3.8

:: Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"

:: Check if conda is available
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: conda is not available in PATH
    echo Please install Anaconda/Miniconda or add it to your PATH
    exit /b 1
)

:: Initialize conda for batch
call conda.bat activate base >nul 2>nul

:: Function to check if environment is active
call :check_env_active
if !ENV_ACTIVE! equ 1 (
    echo Environment %ENV_NAME% is already active
    goto :run_command
)

:: Check if environment exists
conda info --envs | findstr /C:"%ENV_NAME%" >nul
if %errorlevel% neq 0 (
    echo Environment %ENV_NAME% does not exist. Creating it...
    conda create -n %ENV_NAME% python=%PYTHON_VERSION% -y
    if !errorlevel! neq 0 (
        echo ERROR: Failed to create conda environment
        exit /b 1
    )
    
    echo Installing requirements...
    call conda.bat activate %ENV_NAME%
    pip install -r "%SCRIPT_DIR%requirements.txt"
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install requirements
        exit /b 1
    )
) else (
    echo Activating environment %ENV_NAME%...
    call conda.bat activate %ENV_NAME%
    if !errorlevel! neq 0 (
        echo ERROR: Failed to activate environment
        exit /b 1
    )
)

:run_command
:: Handle different command shortcuts
if "%1"=="" (
    echo Usage: %0 [command] [args...]
    echo.
    echo Available shortcuts:
    echo   start       - Start the USDXFixGap application
    echo   test        - Run all tests with pytest
    echo   install     - Install/update requirements ^(auto-detects GPU^)
    echo   install --gpu   - Force GPU/CUDA PyTorch installation
    echo   install --cpu   - Force CPU-only PyTorch installation
    echo   install-dev - Install development dependencies ^(testing, analysis^)
    echo   clean       - Clean cache and temporary files
    echo   shell       - Start interactive Python shell
    echo   info        - Show environment info
    echo   analyze     - Run code quality analysis ^(complexity, style^)
    echo   analyze all - Analyze entire project
    echo   analyze files ^<path^>  - Analyze specific files
    echo   cleanup     - Clean code ^(whitespace, unused imports^)
    echo   cleanup all - Clean entire project
    echo   cleanup --dry-run  - Preview cleanup without changes
    echo.
    echo Or run any Python command directly:
    echo   %0 python script.py
    echo   %0 pip install package
    goto :end
)

if /i "%1"=="start" (
    echo Starting USDXFixGap application...
    cd /d "%SCRIPT_DIR%src"
    python usdxfixgap.py
    goto :end
)

if /i "%1"=="test" (
    echo Running tests...
    cd /d "%SCRIPT_DIR%"
    python -m pytest tests/ -v
    goto :end
)

if /i "%1"=="install" (
    echo Installing/updating requirements...
    
    :: Check for manual GPU/CPU override flags
    set INSTALL_MODE=auto
    if /i "%2"=="--gpu" set INSTALL_MODE=gpu
    if /i "%2"=="--cuda" set INSTALL_MODE=gpu
    if /i "%2"=="--cpu" set INSTALL_MODE=cpu
    
    :: Detect NVIDIA GPU for PyTorch optimization
    echo.
    echo Detecting hardware configuration...
    
    if "!INSTALL_MODE!"=="cpu" (
        echo [Manual Override] Installing CPU-only version as requested
        pip install -r "%SCRIPT_DIR%requirements.txt" --upgrade
        echo.
        echo Installation complete!
        goto :end
    )
    
    if "!INSTALL_MODE!"=="gpu" (
        echo [Manual Override] Installing GPU version as requested
        call :install_gpu
        goto :end
    )
    
    :: Auto-detection mode
    nvidia-smi >nul 2>nul
    if !errorlevel! equ 0 (
        echo [GPU Detected] NVIDIA GPU found - installing PyTorch with CUDA support
        call :install_gpu
        goto :end
    ) else (
        echo [CPU Mode] No NVIDIA GPU detected - installing CPU-only PyTorch
        echo Tip: If you have an NVIDIA GPU, use 'run.bat install --gpu' to force GPU installation
        pip install -r "%SCRIPT_DIR%requirements.txt" --upgrade
        echo.
        echo Installation complete!
        goto :end
    )
)

if /i "%1"=="clean" (
    echo Cleaning cache and temporary files...
    cd /d "%SCRIPT_DIR%"
    if exist "src\cache.db" del "src\cache.db"
    if exist "src\__pycache__" rmdir /s /q "src\__pycache__"
    if exist "tests\__pycache__" rmdir /s /q "tests\__pycache__"
    if exist "output" rmdir /s /q "output"
    for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
    echo Cache cleaned successfully
    goto :end
)

if /i "%1"=="shell" (
    echo Starting Python interactive shell...
    python
    goto :end
)

if /i "%1"=="info" (
    echo Environment Information:
    echo ========================
    conda info
    echo.
    echo Python Version:
    python --version
    echo.
    echo Installed Packages:
    pip list
    goto :end
)

if /i "%1"=="install-dev" (
    echo Installing development dependencies...
    pip install -r "%SCRIPT_DIR%requirements-dev.txt" --upgrade
    echo.
    echo Development dependencies installed!
    echo You can now use:
    echo   - run.bat analyze    ^(code quality analysis^)
    echo   - run.bat cleanup    ^(code cleanup tools^)
    goto :end
)

if /i "%1"=="analyze" (
    echo Running code quality analysis...
    cd /d "%SCRIPT_DIR%"
    
    :: Check if analyze script exists
    if not exist "scripts\analyze_code.py" (
        echo ERROR: scripts\analyze_code.py not found
        echo Make sure you're in the project root directory
        goto :end
    )
    
    :: Determine mode: default to "changed" if %2 is empty or starts with --
    set MODE=changed
    set EXTRA_ARGS=
    if not "%2"=="" (
        echo %2 | findstr /B /C:"--" >nul
        if errorlevel 1 (
            rem %2 doesn't start with --, so it's the mode
            set MODE=%2
            set EXTRA_ARGS=%3 %4 %5 %6
        ) else (
            rem %2 starts with --, so it's an option
            set EXTRA_ARGS=%2 %3 %4 %5
        )
    )
    
    python scripts\analyze_code.py !MODE! !EXTRA_ARGS!
    goto :end
)

if /i "%1"=="cleanup" (
    echo Running code cleanup...
    cd /d "%SCRIPT_DIR%"
    
    :: Check if cleanup script exists
    if not exist "scripts\cleanup_code.py" (
        echo ERROR: scripts\cleanup_code.py not found
        echo Make sure you're in the project root directory
        goto :end
    )
    
    :: Determine mode: default to "changed" if %2 is empty or starts with --
    set MODE=changed
    set EXTRA_ARGS=
    if not "%2"=="" (
        echo %2 | findstr /B /C:"--" >nul
        if errorlevel 1 (
            rem %2 doesn't start with --, so it's the mode
            set MODE=%2
            set EXTRA_ARGS=%3 %4 %5 %6
        ) else (
            rem %2 starts with --, so it's an option
            set EXTRA_ARGS=%2 %3 %4 %5
        )
    )
    
    python scripts\cleanup_code.py !MODE! !EXTRA_ARGS!
    goto :end
)

:: Execute custom command
echo Executing: %*
cd /d "%SCRIPT_DIR%"
%*

:end
endlocal
exit /b %errorlevel%

:: Function to install GPU version of PyTorch
:install_gpu
echo This will enable GPU acceleration for faster processing

:: Install base requirements first (without PyTorch)
pip install -r "%SCRIPT_DIR%requirements.txt" --upgrade

:: Uninstall any existing PyTorch (CPU or CUDA)
echo.
echo Removing existing PyTorch installation...
pip uninstall -y torch torchvision torchaudio 2>nul

:: Install PyTorch with CUDA 12.1 support
echo.
echo Installing PyTorch with CUDA 12.1 support...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

:: Verify CUDA availability
echo.
echo Verifying GPU acceleration...
python -c "import torch; print('GPU Available:', torch.cuda.is_available()); cuda_available = torch.cuda.is_available(); print('GPU:', torch.cuda.get_device_name(0) if cuda_available else 'N/A')"

echo.
echo Installation complete!
goto :eof

:: Function to check if conda environment is active
:check_env_active
set ENV_ACTIVE=0
if not "%CONDA_DEFAULT_ENV%"=="" (
    if "%CONDA_DEFAULT_ENV%"=="%ENV_NAME%" (
        set ENV_ACTIVE=1
    )
)
goto :eof