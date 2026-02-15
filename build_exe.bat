@echo off
echo ================================
echo Building Discord Music Bot .exe
echo ================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Building executable...
echo This may take a few minutes...
echo.

REM Build the exe with system tray support (no console window)
pyinstaller --onefile ^
    --noconsole ^
    --name "DiscordMusicBot" ^
    --icon=NONE ^
    --add-data ".env;." ^
    bot_systray.py

echo.
echo ================================
echo Build complete!
echo ================================
echo.
echo Your executable is in the 'dist' folder: dist\DiscordMusicBot.exe
echo.
echo IMPORTANT:
echo 1. Make sure FFmpeg is installed on your system
echo 2. Copy the .env file to the same folder as the .exe
echo 3. Double-click the .exe to run (it will appear in system tray)
echo.
pause
