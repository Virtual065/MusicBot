# Discord Music Bot - Dockge Deployment

This folder contains everything you need to run the Discord Music Bot using Dockge.

## Quick Start

1. **Download** the `Dockge.zip` file from the latest release
2. **Extract** the zip file
3. **Copy** the `.env.example` file to `.env`
4. **Edit** `.env` and add your Discord bot token:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   ```
5. **Drag and drop** the entire folder into Dockge
6. **Start** the stack

## Files Included

- `docker-compose.yml` - Docker Compose configuration
- `Dockerfile` - Docker image configuration
- `bot.py` - The bot source code
- `requirements.txt` - Python dependencies
- `.env.example` - Example environment file

## Getting Your Discord Bot Token

1. Go to https://discord.com/developers/applications
2. Create a new application or select an existing one
3. Go to the "Bot" section
4. Click "Reset Token" and copy your token
5. Paste it into the `.env` file

## Support

For issues and support, visit: https://github.com/yourusername/discord-music-bot
