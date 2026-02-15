# Quick Start Guide

## 🚀 Fastest Way to Get Started

Your Discord bot is **already configured** with your token! Here are your options:

### Option 1: Run with Dockge (Easiest - No installation needed)

1. **Drag and drop** the entire `MusicBot` folder into your Dockge stacks directory
2. In Dockge web interface, start the stack
3. Done! The bot is now online

### Option 2: Run as System Tray App (Windows)

**If you have Python installed:**

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python bot_systray.py
```

The bot will appear in your system tray. Hover over it to see stats!

**If you want an .exe file:**

1. Double-click `build_exe.bat`
2. Wait for it to build
3. Your .exe will be in the `dist` folder
4. Copy the .exe and the `.env` file to anywhere you want
5. Double-click the .exe to run

### Option 3: Run in Console (Windows/Mac/Linux)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python bot.py
```

## 📝 Using the Bot

1. Join a voice channel in Discord
2. Type in any text channel:
   ```
   !play https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```
3. Enjoy the music!

## 🎮 Commands

- `!play [url]` - Play music from a URL
- `!pause` - Pause the song
- `!resume` - Resume the song
- `!stop` - Stop and disconnect
- `!help_music` - Show all commands

## ⚙️ Requirements

**For Local/EXE Version:**
- FFmpeg must be installed
  - Windows: Download from https://ffmpeg.org/download.html and add to PATH
  - Mac: `brew install ffmpeg`
  - Linux: `sudo apt-get install ffmpeg`

**For Dockge/Docker Version:**
- Nothing! FFmpeg is included in the Docker image

## 🔧 Troubleshooting

**Bot doesn't respond:**
- Make sure "MESSAGE CONTENT INTENT" is enabled in Discord Developer Portal
  - Go to https://discord.com/developers/applications
  - Select your app
  - Go to Bot → Privileged Gateway Intents
  - Enable "MESSAGE CONTENT INTENT"

**Can't hear audio:**
- Make sure FFmpeg is installed (if running locally)
- Check bot has "Connect" and "Speak" permissions in your Discord server

**System tray version:**
- Hover over the tray icon to see CPU, Memory, and Uptime
- Right-click for menu options
- The bot runs completely hidden - no window!

## 📦 What's Included

- `bot.py` - Console version
- `bot_systray.py` - System tray version with resource monitoring
- `build_exe.bat` - Easy .exe builder
- `docker-compose.yml` - For Dockge/Docker deployment
- `.env` - Your token is already configured!

## 🎯 Next Steps

For more detailed information, see `README.md`.

Happy listening! 🎵
