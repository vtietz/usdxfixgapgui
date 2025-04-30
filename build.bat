pyinstaller --onefile --icon="%~dp0src\assets\usdxfixgap-icon.ico" "%~dp0src\usdxfixgap.py"
copy "%~dp0src\config.ini" dist\