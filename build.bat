@echo off
echo Installing PyInstaller if not present...
pip install pyinstaller --quiet

echo.
echo Building PyPhast...
pyinstaller PyPhast.spec --clean

echo.
echo Done! Executable is in: dist\PyPhast\PyPhast.exe
pause
