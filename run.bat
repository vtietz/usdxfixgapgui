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
    echo   start       - Start the USDX FixGap application
    echo   test        - Run all tests with pytest
    echo   test --docs - Run tests and generate Tier-1/Tier-3 visual artifacts
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
    echo   build       - Build Windows onefile executable with PyInstaller
    echo   build portable - Build portable onedir executable with _internal folder
    echo   set-version ^<version^> - Set version in VERSION file, create Git tag, and push
    echo                           Example: run.bat set-version v1.2.0-rc6
    echo.
    echo Or run any Python command directly:
    echo   %0 python script.py
    echo   %0 pip install package
    goto :end
)

if /i "%1"=="start" (
    echo Starting USDX FixGap application...
    cd /d "%SCRIPT_DIR%src"
    :: Forward all arguments after "start" to the Python script
    "%VENV_PYTHON%" usdxfixgap.py %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

if /i "%1"=="test" (
    echo Running tests...
    cd /d "%SCRIPT_DIR%"

    :: Check for --docs flag
    set TEST_DOCS=
    set PYTEST_ARGS=

    :: Parse arguments
    if /i "%2"=="--docs" set TEST_DOCS=1
    if /i "%2"=="--artifacts" set TEST_DOCS=1
    if /i "%3"=="--docs" set TEST_DOCS=1
    if /i "%3"=="--artifacts" set TEST_DOCS=1

    :: Collect pytest args (skip our custom flags)
    if /i not "%2"=="--docs" if /i not "%2"=="--artifacts" set PYTEST_ARGS=%PYTEST_ARGS% %2
    if /i not "%3"=="--docs" if /i not "%3"=="--artifacts" set PYTEST_ARGS=%PYTEST_ARGS% %3
    if /i not "%4"=="" set PYTEST_ARGS=%PYTEST_ARGS% %4 %5 %6 %7 %8 %9

    :: Set environment variables for doc generation
    if defined TEST_DOCS (
        set GAP_WRITE_DOCS=1
        echo [Test Artifacts] Visual artifacts will be generated in docs/gap-tests/
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
    echo.
    echo Step 1: Installing base requirements...
    "%VENV_PIP%" install -r "%SCRIPT_DIR%requirements.txt" --upgrade
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install base requirements
        exit /b 1
    )

    echo.
    echo Step 2: Installing development tools...
    "%VENV_PIP%" install -r "%SCRIPT_DIR%requirements-dev.txt" --upgrade
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install development dependencies
        exit /b 1
    )

    echo.
    echo Development environment ready!
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

if /i "%1"=="build" (
    :: Determine build mode and spec file
    set BUILD_MODE=onefile
    set SPEC_FILE=usdxfixgap.spec
    set OUTPUT_DESC=dist\usdxfixgap.exe

    if /i "%2"=="portable" (
        set BUILD_MODE=portable
        set SPEC_FILE=usdxfixgap-onedir.spec
        set OUTPUT_DESC=dist\portable\ ^(directory with _internal folder^)
    )

    echo ==========================================
    echo Building USDX FixGap Executable ^(!BUILD_MODE!^)
    echo ==========================================
    echo.
    cd /d "%SCRIPT_DIR%"

    :: Detect platform-specific requirements file (Windows uses standard requirements-build.txt)
    set REQUIREMENTS_FILE=requirements-build.txt
    if exist "%SCRIPT_DIR%requirements-build.txt" (
        echo Using build requirements: requirements-build.txt
    ) else (
        echo WARNING: requirements-build.txt not found, using requirements.txt
        set REQUIREMENTS_FILE=requirements.txt
    )

    :: Check if PyInstaller is installed
    "%VENV_PIP%" show pyinstaller >nul 2>nul
    if !errorlevel! neq 0 (
        echo PyInstaller not found. Installing...
        "%VENV_PIP%" install pyinstaller==6.16.0
        if !errorlevel! neq 0 (
            echo ERROR: Failed to install PyInstaller
            exit /b 1
        )
    )

    :: Install build dependencies
    echo Installing build dependencies from !REQUIREMENTS_FILE!...
    "%VENV_PIP%" install --no-cache-dir -r "%SCRIPT_DIR%!REQUIREMENTS_FILE!"
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install build dependencies
        exit /b 1
    )

    :: Build with PyInstaller using spec file
    echo Building executable ^(this may take a few minutes^)...
    echo NOTE: Bundling CPU-only PyTorch. Users can upgrade to GPU via GPU Pack download.

    :: Check if spec file exists
    if not exist "%SCRIPT_DIR%!SPEC_FILE!" (
        echo ERROR: !SPEC_FILE! not found
        echo Please make sure the spec file exists in the project root
        exit /b 1
    )

    "%VENV_PYTHON%" -m PyInstaller --clean --noconfirm "%SCRIPT_DIR%!SPEC_FILE!"

    if !errorlevel! equ 0 (
        echo.
        echo ==========================================
        echo Build completed successfully!
        echo ==========================================
        echo.

        REM Organize builds into subdirectories
        if /i "!BUILD_MODE!"=="onefile" (
            if not exist "%SCRIPT_DIR%dist\onefile" mkdir "%SCRIPT_DIR%dist\onefile"
            if exist "%SCRIPT_DIR%dist\usdxfixgap.exe" (
                move /Y "%SCRIPT_DIR%dist\usdxfixgap.exe" "%SCRIPT_DIR%dist\onefile\usdxfixgap.exe" >nul
                echo Output: %SCRIPT_DIR%dist\onefile\usdxfixgap.exe
            )
        ) else (
            REM Move portable build contents directly into dist\portable\
            if exist "%SCRIPT_DIR%dist\usdxfixgap-portable" (
                if not exist "%SCRIPT_DIR%dist\portable" mkdir "%SCRIPT_DIR%dist\portable"
                REM Move all contents from usdxfixgap-portable to portable
                xcopy /E /I /Y "%SCRIPT_DIR%dist\usdxfixgap-portable\*" "%SCRIPT_DIR%dist\portable\" >nul
                rmdir /S /Q "%SCRIPT_DIR%dist\usdxfixgap-portable"
                echo Output: %SCRIPT_DIR%dist\portable\ ^(with _internal folder^)
            )
        )
    ) else (
        echo.
        echo ==========================================
        echo Build failed!
        echo ==========================================
        exit /b 1
    )
    goto :end
)

if /i "%1"=="set-version" (
    if "%2"=="" (
        echo ERROR: Version argument required
        echo Usage: run.bat set-version ^<version^>
        echo Example: run.bat set-version v1.2.0-rc6
        exit /b 1
    )

    set VERSION=%2
    echo ==========================================
    echo Setting version: !VERSION!
    echo ==========================================
    echo.

    :: Write version to VERSION file
    echo !VERSION!> "%SCRIPT_DIR%VERSION"
    echo [1/5] Updated VERSION file

    :: Check if we're in a git repository
    git rev-parse --git-dir >nul 2>nul
    if !errorlevel! neq 0 (
        echo ERROR: Not a git repository
        exit /b 1
    )

    :: Stage and commit VERSION file
    git add "%SCRIPT_DIR%VERSION"
    echo [2/5] Staged VERSION file

    git commit -m "Chore: Set version to !VERSION!"
    if !errorlevel! neq 0 (
        echo ERROR: Failed to commit VERSION file
        echo Note: File may already be committed with this version
        exit /b 1
    )
    echo [3/5] Committed VERSION file

    :: Push commit before creating tag
    echo Pushing commit to remote...
    git push
    if !errorlevel! neq 0 (
        echo ERROR: Failed to push commit
        exit /b 1
    )
    echo [4/5] Pushed commit to remote

    :: Create or overwrite tag (force)
    git tag -f !VERSION! -m "Release !VERSION!"
    if !errorlevel! neq 0 (
        echo ERROR: Failed to create git tag
        exit /b 1
    )
    echo [5/5] Created git tag: !VERSION!

    :: Push tag (force to overwrite if exists)
    echo Pushing tag to remote...
    git push origin !VERSION! --force
    if !errorlevel! neq 0 (
        echo ERROR: Failed to push tag
        echo You may need to push manually: git push origin !VERSION! --force
        exit /b 1
    )
    echo [6/6] Pushed tag to remote

    echo.
    echo ==========================================
    echo Version !VERSION! set successfully!
    echo ==========================================
    echo.
    echo The VERSION file has been committed and the tag has been created and pushed.
    echo GitHub Actions will automatically build release artifacts.
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
