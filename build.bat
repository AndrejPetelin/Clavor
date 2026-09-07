@echo off
setlocal
echo.
echo ─────────────────────────────────────────────────────────
echo   Clavor — build script
echo ─────────────────────────────────────────────────────────
echo.

:: Install / update dependencies
echo [1/2] Installing dependencies...
pip install --upgrade pynput pyinstaller
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause & exit /b 1
)
echo.

:: Build
echo [2/2] Building executable...
pyinstaller Clavor.spec --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    pause & exit /b 1
)

echo.
echo ─────────────────────────────────────────────────────────
echo   Done!  dist\Clavor.exe
echo ─────────────────────────────────────────────────────────
echo.
pause
