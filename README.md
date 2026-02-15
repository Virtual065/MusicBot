# 🎵 Discord Music Bot

A feature-rich Discord music bot with queue management, playlist support, auto-pause, and system tray integration.

## ✨ Features

### 🎮 Commands
- **`/help`** - Get information on other commands
- **`/play [url]`** - Play music from YouTube
- **`/queue`** - View queue with pagination
- **`/nonstoppop [start/stop]`** - Shuffle playlist mode
- **`/skip`** - Skip current song
- **`/pause`** - Pause/resume playback
- **`/previous`** - Play previous song (tracks last 10)
- **`/queueclear`** - Clear entire queue
- **`/stop`** - Stop and disconnect
- **`/regulate`** - Owner-only mode toggle

### 🚀 Smart Features
- ⏸️ Auto-pause when alone in voice channel
- 🚪 Auto-disconnect after 5 minutes alone
- 👁️ All responses are ephemeral (private)
- 📊 Live resource monitoring (Windows .exe)
- 🟥 System tray icon (Windows .exe)

## 📥 Installation

### Windows (.exe) - Easiest!

1. **Download** `DiscordMusicBot.exe` from [Releases](../../releases)
2. **Run** the .exe - look for red square (🟥) in system tray
3. **First run:** Setup window appears - enter your Discord bot token
4. **Done!** Bot is running in the background

**Managing:**
- Hover over 🟥 to see "Discord Music Bot"
- Right-click → "Show Stats" for live monitoring
- Right-click → "Quit" to exit

### Dockge/Docker

1. **Download** `Dockge.zip` from [Releases](../../releases)
2. **Extract** the zip
3. **Edit** `.env` file with your token:
   ```
   DISCORD_TOKEN=your_token_here
   ```
4. **Drag** folder into Dockge
5. **Start** the stack

### From Source

```bash
git clone https://github.com/yourusername/discord-music-bot.git
cd discord-music-bot
pip install -r requirements.txt

# Create .env file
echo "DISCORD_TOKEN=your_token_here" > .env

# Run console version
python bot.py

# OR run system tray version (Windows)
python bot_systray.py
```

## 🔑 Getting Your Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create application → Bot section → Reset Token
3. **Enable Intents:**
   - Message Content
   - Server Members
   - Presence
4. **OAuth2 → URL Generator:**
   - Scopes: `bot` + `applications.commands`
   - Permissions: Send Messages, Connect, Speak
5. Copy URL and invite bot to server

## 📁 Project Structure

```
discord-music-bot/
├── bot.py                 # Console version
├── bot_systray.py        # System tray version
├── requirements.txt
├── .env.example
├── Dockge/              # Docker deployment
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── bot.py
│   ├── requirements.txt
│   └── .env.example
└── .github/
    └── workflows/
        └── release.yml   # Auto-release on push to production
```

## 🔧 Development

### Build .exe

```bash
pip install pyinstaller
python -m PyInstaller --clean --onefile --noconsole --name "DiscordMusicBot" bot_systray.py
```

Output: `dist/DiscordMusicBot.exe`

### Branches

- **`production`** - Stable releases (auto-builds .exe + Dockge.zip)
- **`staging`** - Development and testing

### Release Process

1. Test on `staging`
2. Merge to `production`:
   ```bash
   git checkout production
   git merge staging
   git push
   ```
3. GitHub Actions auto-creates draft release
4. Edit and publish release

## ⚙️ Configuration

### Windows .exe

Creates `Info.txt` on first run:
```
DISCORD_TOKEN=your_token
```

### Docker/Source

Create `.env` file:
```
DISCORD_TOKEN=your_token
```

## 🐛 Troubleshooting

### Bot won't connect
- Verify token in `Info.txt` or `.env`
- Check bot permissions in server

### No audio
- Ensure bot has Connect/Speak permissions
- FFmpeg required (included in Docker, manual for source)

### .exe won't start
- Windows may block - Right-click → Properties → Unblock
- Check `musicbot.log` for errors

## 🤝 Contributing

1. Fork repository
2. Create branch from `staging`
3. Make changes
4. PR to `staging`

## 📄 License

MIT License - Free to use and modify

## ⚠️ Important

- **Never share** `Info.txt` or `.env` - contains your bot token
- .exe runs in system tray - look for red square 🟥
- All commands are private (ephemeral)

## 📞 Support

Issues or questions? [Open an issue](../../issues)

---

Made with ❤️ for Discord

