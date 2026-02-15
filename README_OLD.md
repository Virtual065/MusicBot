# Discord Music Bot

A simple and easy-to-use Discord bot that plays music from URLs (YouTube, SoundCloud, etc.) in voice channels.

## Features

- 🎵 Play music from URLs (YouTube, SoundCloud, and more)
- 🔊 Automatically joins your voice channel
- ⏸️ Pause/Resume controls
- ⏹️ Stop and disconnect
- 💻 System tray application (runs hidden in taskbar)
- 📊 Real-time resource monitoring (CPU, Memory, Uptime)
- 🐳 Docker support for easy deployment with Dockge

## Commands

- `!play [url]` - Play music from a URL
- `!stop` - Stop playing and disconnect from voice channel
- `!pause` - Pause the current song
- `!resume` - Resume the paused song
- `!help_music` - Show all available commands

## Setup Instructions

### Prerequisites

1. **Create a Discord Bot:**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" and give it a name
   - Go to the "Bot" tab and click "Add Bot"
   - Under "Privileged Gateway Intents", enable:
     - MESSAGE CONTENT INTENT
     - SERVER MEMBERS INTENT
     - PRESENCE INTENT
   - Copy the bot token (you'll need this later)

2. **Invite the Bot to Your Server:**
   - Go to the "OAuth2" > "URL Generator" tab
   - Select scopes: `bot`
   - Select bot permissions:
     - Send Messages
     - Connect
     - Speak
     - Use Voice Activity
   - Copy the generated URL and open it in your browser
   - Select your server and authorize the bot

### Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Discord bot token:
   ```
   DISCORD_TOKEN=your_actual_discord_token_here
   ```

## Deployment Options

### Option 1: Deploy with Dockge (Recommended)

1. **Copy the entire MusicBot folder to your Dockge stacks directory**

2. **In Dockge:**
   - Navigate to your Dockge web interface
   - Click "Add Stack" or import the folder
   - The stack will automatically detect the `docker-compose.yml` file
   - Make sure to edit the `.env` file with your Discord token
   - Click "Deploy" or "Start"

3. **That's it!** The bot will start running in Docker.

### Option 2: Run with Docker Compose (Manual)

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

### Option 3: Run Locally (Without Docker)

**Requirements:**
- Python 3.11 or higher
- FFmpeg installed on your system

**Steps:**

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Make sure FFmpeg is installed:
   - **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
   - **Linux:** `sudo apt-get install ffmpeg`
   - **macOS:** `brew install ffmpeg`

3. Create `.env` file with your Discord token (see Configuration above)

4. Run the bot:
   ```bash
   python bot.py
   ```

### Option 4: Run as System Tray Application (Windows - Recommended for Desktop)

**System Tray Version** - Runs hidden in the Windows taskbar with resource monitoring!

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Make sure FFmpeg is installed (see Option 3 for FFmpeg installation)

3. Run the system tray version:
   ```bash
   python bot_systray.py
   ```

**Features:**
- Runs silently in the system tray (no visible window)
- Hover over the tray icon to see:
  - Bot status (Online, Playing, Paused)
  - CPU usage
  - Memory usage
  - Uptime
- Right-click the tray icon for options:
  - Show Stats (detailed statistics)
  - Quit (close the bot)

### Option 5: Create .exe (Windows - System Tray Version)

**Easy Method** - Use the provided batch script:

1. Simply double-click `build_exe.bat`
2. Wait for the build to complete
3. Find the .exe in the `dist` folder

**Manual Method:**

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

2. Run the build command:
   ```bash
   pyinstaller --onefile --noconsole --name DiscordMusicBot bot_systray.py
   ```

3. The .exe will be in the `dist` folder

**To use the .exe:**
1. Copy `DiscordMusicBot.exe` from the `dist` folder to anywhere
2. Make sure you have a `.env` file in the same folder as the .exe
3. Make sure FFmpeg is installed on your system and added to PATH
4. Double-click the .exe - it will appear in your system tray
5. Hover over the tray icon to see resource usage
6. Right-click for options

**Note:** The bot runs completely hidden - no console window. It only appears as an icon in the system tray.

## Usage Examples

1. **Join a voice channel** in your Discord server

2. **In any text channel**, type:
   ```
   !play https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

3. The bot will:
   - Join your voice channel
   - Download and play the audio from the URL
   - Show the song title

## Troubleshooting

### Bot doesn't respond
- Make sure MESSAGE CONTENT INTENT is enabled in Discord Developer Portal
- Check that the bot has permission to read messages in the channel

### Bot can't play audio
- Ensure FFmpeg is installed
- Check that the bot has "Connect" and "Speak" permissions in the voice channel

### Bot disconnects immediately
- Check the container logs: `docker-compose logs -f`
- Verify your Discord token is correct in the `.env` file

### "Not in a voice channel" error
- You must be in a voice channel before using `!play`

## File Structure

```
MusicBot/
├── bot.py                  # Main bot code (console version)
├── bot_systray.py         # System tray version with resource monitoring
├── build_exe.bat          # Easy build script for creating .exe
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker Compose configuration
├── .env.example           # Example environment file
├── .env                   # Your actual environment file (already configured)
├── .gitignore            # Git ignore file
└── README.md             # This file
```

## Support

If you encounter any issues, make sure:
1. Your Discord token is correct
2. The bot has proper permissions in your server
3. You're in a voice channel when using `!play`
4. FFmpeg is installed (if running locally)

## License

Free to use and modify as needed.
