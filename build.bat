@echo off
echo ==========================================
echo Building USDXFixGap Executable
echo ==========================================
echo.

:: Get script directory
set "SCRIPT_DIR=%~dp0"

:: Build with PyInstaller
:: Excludes development/testing libraries to reduce size
echo Building executable (this may take a few minutes)...
pyinstaller --onefile ^
    --windowed ^
    --icon="%SCRIPT_DIR%src\assets\usdxfixgap-icon.ico" ^
    --add-data "%SCRIPT_DIR%src\assets;assets" ^
    --exclude-module pytest ^
    --exclude-module pytest-qt ^
    --exclude-module pytest-mock ^
    --exclude-module lizard ^
    --exclude-module flake8 ^
    --exclude-module mypy ^
    --exclude-module autoflake ^
    --exclude-module IPython ^
    --exclude-module jupyter ^
    --exclude-module notebook ^
    --name usdxfixgap ^
    "%SCRIPT_DIR%src\usdxfixgap.py"

if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo Build completed successfully!
    echo ==========================================
    echo.
    echo Executable: %SCRIPT_DIR%dist\usdxfixgap.exe
) else (
    echo.
    echo ==========================================
    echo Build failed!
    echo ==========================================
    exit /b 1
)
