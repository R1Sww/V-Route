@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo [2/3] Generating icon...
python tools\make_icon.py
if errorlevel 1 exit /b 1

echo [3/3] Building driverless EXE...
pyinstaller --noconfirm --clean V-Route.spec
if errorlevel 1 exit /b 1

echo.
echo Done: %~dp0dist\V-Route.exe
endlocal
