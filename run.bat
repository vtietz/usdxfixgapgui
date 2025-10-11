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
    call conda activate %ENV_NAME%
    pip install -r "%SCRIPT_DIR%requirements.txt"
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install requirements
        exit /b 1
    )
) else (
    echo Activating environment %ENV_NAME%...
    call conda activate %ENV_NAME%
)

:run_command
:: Handle different command shortcuts
if "%1"=="" (
    echo Usage: %0 [command] [args...]
    echo.
    echo Available shortcuts:
    echo   start    - Start the USDXFixGap application
    echo   test     - Run all tests with pytest
    echo   install  - Install/update requirements
    echo   clean    - Clean cache and temporary files
    echo   shell    - Start interactive Python shell
    echo   info     - Show environment info
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
    pip install -r "%SCRIPT_DIR%requirements.txt" --upgrade
    goto :end
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

:: Execute custom command
echo Executing: %*
cd /d "%SCRIPT_DIR%"
%*

:end
endlocal
exit /b %errorlevel%

:: Function to check if conda environment is active
:check_env_active
set ENV_ACTIVE=0
if not "%CONDA_DEFAULT_ENV%"=="" (
    if "%CONDA_DEFAULT_ENV%"=="%ENV_NAME%" (
        set ENV_ACTIVE=1
    )
)
goto :eof