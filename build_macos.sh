#!/bin/bash
# macOS build script for USDXFixGap
echo "=========================================="
echo "Building USDXFixGap Executable (macOS)"
echo "=========================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build with PyInstaller
# Excludes development/testing libraries to reduce size
echo "Building executable (this may take a few minutes)..."
pyinstaller --onefile \
  --windowed \
  --icon="$SCRIPT_DIR/src/assets/usdxfixgap-icon.ico" \
  --add-data "$SCRIPT_DIR/src/assets:assets" \
  --exclude-module pytest \
  --exclude-module pytest-qt \
  --exclude-module pytest-mock \
  --exclude-module lizard \
  --exclude-module flake8 \
  --exclude-module mypy \
  --exclude-module autoflake \
  --exclude-module IPython \
  --exclude-module jupyter \
  --exclude-module notebook \
  --name usdxfixgap \
  "$SCRIPT_DIR/src/usdxfixgap.py"

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "Build completed successfully!"
    echo "=========================================="
    echo ""
    echo "Executable: $SCRIPT_DIR/dist/usdxfixgap"
else
    echo ""
    echo "=========================================="
    echo "Build failed!"
    echo "=========================================="
    exit 1
fi
