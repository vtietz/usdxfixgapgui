@echo off
setlocal EnableDelayedExpansion

:: Configuration
set VENV_DIR=.venv
set PYTHON_VERSION=3.10

:: Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%SCRIPT_DIR%%VENV_DIR%\Scripts\pip.exe"

:: Bootstrap venv if missing
if not exist "%VENV_PYTHON%" (
    echo Virtual environment not found. Creating at %VENV_DIR%...
    
    :: Detect system Python (prefer py launcher with version selection)
    set "SYS_PYTHON="
    py -3.10 --version >nul 2>nul
    if !errorlevel! equ 0 (
        set "SYS_PYTHON=py -3.10"
        echo Using Python 3.10 via py launcher
    ) else (
        py -3.8 --version >nul 2>nul
        if !errorlevel! equ 0 (
            set "SYS_PYTHON=py -3.8"
            echo Using Python 3.8 via py launcher
        ) else (
            where python >nul 2>nul
            if !errorlevel! equ 0 (
                set "SYS_PYTHON=python"
                echo Using system python
            ) else (
                echo ERROR: No Python installation found
                echo Please install Python 3.8+ from https://www.python.org/
                exit /b 1
            )
        )
    )
    
    :: Create venv
    !SYS_PYTHON! -m venv "%SCRIPT_DIR%%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo ERROR: Failed to create virtual environment
        echo Make sure Python venv module is available
        exit /b 1
    )
    
    echo Upgrading pip...
    "%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel
    if !errorlevel! neq 0 (
        echo ERROR: Failed to upgrade pip
        exit /b 1
    )
    
    echo Installing requirements...
    "%VENV_PIP%" install -r "%SCRIPT_DIR%requirements.txt"
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install requirements
        exit /b 1
    )
    echo Virtual environment created successfully
)

:run_command
:: Handle different command shortcuts
if "%1"=="" (
    echo Usage: %0 [command] [args...]
    echo.
    echo Available shortcuts:
    echo   start       - Start the USDXFixGap application
    echo   test        - Run all tests with pytest
    echo   test --docs - Run tests and generate Tier-1/Tier-3 visual artifacts
    echo   test --config - Run tests with config.ini values ^(validate your settings^)
    echo   test --docs --config - Generate artifacts using your config.ini values
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
    "%VENV_PYTHON%" usdxfixgap.py
    goto :end
)

if /i "%1"=="test" (
    echo Running tests...
    cd /d "%SCRIPT_DIR%"
    
    :: Check for flags (--docs, --artifacts, --config)
    set TEST_DOCS=
    set TEST_CONFIG=
    set PYTEST_ARGS=
    
    :: Parse all arguments
    if /i "%2"=="--docs" set TEST_DOCS=1
    if /i "%2"=="--artifacts" set TEST_DOCS=1
    if /i "%2"=="--config" set TEST_CONFIG=1
    if /i "%3"=="--docs" set TEST_DOCS=1
    if /i "%3"=="--artifacts" set TEST_DOCS=1
    if /i "%3"=="--config" set TEST_CONFIG=1
    if /i "%4"=="--docs" set TEST_DOCS=1
    if /i "%4"=="--artifacts" set TEST_DOCS=1
    if /i "%4"=="--config" set TEST_CONFIG=1
    
    :: Collect pytest args (skip our custom flags)
    if /i not "%2"=="--docs" if /i not "%2"=="--artifacts" if /i not "%2"=="--config" set PYTEST_ARGS=%PYTEST_ARGS% %2
    if /i not "%3"=="--docs" if /i not "%3"=="--artifacts" if /i not "%3"=="--config" set PYTEST_ARGS=%PYTEST_ARGS% %3
    if /i not "%4"=="--docs" if /i not "%4"=="--artifacts" if /i not "%4"=="--config" set PYTEST_ARGS=%PYTEST_ARGS% %4
    if /i not "%5"=="" set PYTEST_ARGS=%PYTEST_ARGS% %5 %6 %7 %8 %9
    
    :: Set environment variables based on flags
    if defined TEST_DOCS (
        set GAP_TIER1_WRITE_DOCS=1
        set GAP_TIER3_WRITE_DOCS=1
        echo [Test Artifacts] Visual artifacts will be generated in docs/gap-tests/
    )
    if defined TEST_CONFIG (
        set GAP_TEST_USE_CONFIG_INI=1
        echo [Config Testing] Tests will use values from config.ini
    )
    
    "%VENV_PYTHON%" -m pytest tests/ -q %PYTEST_ARGS%
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
        "%VENV_PIP%" install -r "%SCRIPT_DIR%requirements.txt" --upgrade
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
        "%VENV_PIP%" install -r "%SCRIPT_DIR%requirements.txt" --upgrade
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
    for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
    echo Cache cleaned successfully
    goto :end
)

if /i "%1"=="shell" (
    echo Starting Python interactive shell...
    "%VENV_PYTHON%"
    goto :end
)

if /i "%1"=="info" (
    echo Environment Information:
    echo ========================
    echo Virtual Environment: %VENV_DIR%
    echo.
    echo Python Version:
    "%VENV_PYTHON%" --version
    echo.
    echo Python Location:
    where "%VENV_PYTHON%"
    echo.
    echo Installed Packages:
    "%VENV_PIP%" list
    goto :end
)

if /i "%1"=="install-dev" (
    echo Installing development dependencies...
    "%VENV_PIP%" install -r "%SCRIPT_DIR%requirements-dev.txt" --upgrade
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
    
    "%VENV_PYTHON%" scripts\analyze_code.py !MODE! !EXTRA_ARGS!
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
    
    "%VENV_PYTHON%" scripts\cleanup_code.py !MODE! !EXTRA_ARGS!
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
"%VENV_PIP%" install -r "%SCRIPT_DIR%requirements.txt" --upgrade

:: Uninstall any existing PyTorch (CPU or CUDA)
echo.
echo Removing existing PyTorch installation...
"%VENV_PIP%" uninstall -y torch torchvision torchaudio 2>nul

:: Install PyTorch with CUDA 12.1 support
echo.
echo Installing PyTorch with CUDA 12.1 support...
"%VENV_PIP%" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

:: Verify CUDA availability
echo.
echo Verifying GPU acceleration...
"%VENV_PYTHON%" -c "import torch; print('GPU Available:', torch.cuda.is_available()); cuda_available = torch.cuda.is_available(); print('GPU:', torch.cuda.get_device_name(0) if cuda_available else 'N/A')"

echo.
echo Installation complete!
goto :eof