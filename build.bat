pyinstaller --onefile --windowed --icon="%~dp0src\assets\usdxfixgap-icon.ico" --add-data "%~dp0src\assets;assets" "%~dp0src\usdxfixgap.py"
copy "%~dp0src\config.ini" dist\