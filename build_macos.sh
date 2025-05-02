#!/bin/bash
# macOS build script
pyinstaller --onefile --windowed --icon="$(pwd)/src/assets/usdxfixgap-icon.ico" \
  --add-data "$(pwd)/src/assets:assets" \
  "$(pwd)/src/usdxfixgap.py"