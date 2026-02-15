import discord
from discord import app_commands
from discord.ext import commands, tasks
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime
import random

# Load environment variables
load_dotenv()

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix='/', intents=intents)

# Music queue system - per guild
music_queues = {}
nonstop_pop_mode = {}
last_activity = {}
currently_playing = {}  # Track currently playing song
previous_songs = {}  # Track previous songs for /previous
regulated_mode = {}  # Track if guild is in regulated mode (owner only)
command_logs = {}  # Store command history per guild (max 50)
manual_pause = {}  # Track manual pause by user (don't auto-resume)

# Playlist URL
NONSTOP_POP_PLAYLIST = "https://youtube.com/playlist?list=PLgbI0QcBNn5isOvlIN0rRK9Y6bSQdheii&si=Cqb7oJDTsYBDHXLz"

# yt-dlp options
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,  # Allow playlists
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.webpage_url = data.get('webpage_url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # Return all entries for playlists
            return data['entries']

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)


def get_queue(guild_id):
    """Get or create queue for a guild"""
    if guild_id not in music_queues:
        music_queues[guild_id] = []
    return music_queues[guild_id]


def log_command(guild_id: int, user_name: str, command_name: str, details: str = ""):
    """Log a command to the guild's command history (max 50 entries)"""
    if guild_id not in command_logs:
        command_logs[guild_id] = []

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "user": user_name,
        "command": command_name,
        "details": details
    }

    command_logs[guild_id].insert(0, log_entry)  # Add to front

    # Keep only the last 50 entries
    if len(command_logs[guild_id]) > 50:
        command_logs[guild_id] = command_logs[guild_id][:50]


async def play_next(guild, skip_previous_tracking=False):
    """Play the next song in the queue"""
    queue = get_queue(guild.id)

    if len(queue) == 0:
        # Queue is empty, update last activity
        last_activity[guild.id] = datetime.now()
        currently_playing[guild.id] = None
        return

    voice_client = guild.voice_client
    if not voice_client:
        return

    # Get next song
    next_song = queue.pop(0)

    # Track previous song if not skipping
    if not skip_previous_tracking and guild.id in currently_playing and currently_playing[guild.id]:
        if guild.id not in previous_songs:
            previous_songs[guild.id] = []
        previous_songs[guild.id].append(currently_playing[guild.id])
        # Keep only last 10 previous songs
        if len(previous_songs[guild.id]) > 10:
            previous_songs[guild.id].pop(0)

    try:
        # Create audio source
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(next_song['url'], download=False))

        if 'entries' in data:
            data = data['entries'][0]

        player = YTDLSource(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), data=data)

        # Store currently playing
        currently_playing[guild.id] = next_song

        def after_playing(error):
            if error:
                print(f'Player error: {error}')
            # Play next song
            asyncio.run_coroutine_threadsafe(play_next(guild), bot.loop)

        voice_client.play(player, after=after_playing)
        last_activity[guild.id] = datetime.now()

        # Update NonStopPop mode status
        if guild.id in nonstop_pop_mode and nonstop_pop_mode[guild.id]:
            print(f"[NonStopPop] Now playing: {player.title}")
        else:
            print(f"Now playing: {player.title}")

    except Exception as e:
        print(f'Error playing next song: {e}')
        # Try next song in queue
        await play_next(guild)


@tasks.loop(seconds=30)
async def check_empty_vc():
    """Check for empty voice channels - pause immediately, disconnect after 5 minutes"""
    current_time = datetime.now()

    for guild in bot.guilds:
        voice_client = guild.voice_client

        if voice_client and voice_client.channel:
            # Count members excluding bots
            members = [m for m in voice_client.channel.members if not m.bot]

            if len(members) == 0:
                # Pause immediately if playing and not already paused
                if voice_client.is_playing():
                    voice_client.pause()
                    print(f"Paused playback in {guild.name} - VC is empty")
                    # Don't set manual_pause flag - this is auto-pause

                # VC is empty
                if guild.id in last_activity:
                    time_diff = (current_time - last_activity[guild.id]).total_seconds()

                    if time_diff >= 300:  # 5 minutes
                        print(f"Disconnecting from {guild.name} - VC empty for 5 minutes")
                        await voice_client.disconnect()
                        # Clear queue
                        if guild.id in music_queues:
                            music_queues[guild.id] = []
                        if guild.id in nonstop_pop_mode:
                            nonstop_pop_mode[guild.id] = False
                        if guild.id in currently_playing:
                            currently_playing[guild.id] = None
                else:
                    last_activity[guild.id] = current_time
            else:
                # Resume if paused when people rejoin (only if not manually paused)
                if voice_client.is_paused():
                    # Only auto-resume if user didn't manually pause
                    if guild.id not in manual_pause or not manual_pause[guild.id]:
                        voice_client.resume()
                        print(f"Resumed playback in {guild.name} - users rejoined")

                # VC has people, update last activity
                last_activity[guild.id] = current_time


@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')
    print(f'Bot ID: {bot.user.id}')
    print('Syncing slash commands...')

    try:
        synced = await bot.tree.sync()
        print(f'Successfully synced {len(synced)} slash command(s)')
        for cmd in synced:
            print(f'  - /{cmd.name}')
    except Exception as e:
        print(f'Error syncing commands: {e}')

    # Start empty VC checker
    check_empty_vc.start()
    print('------')


@bot.tree.command(name="play", description="Add a song to the queue")
@app_commands.describe(url="YouTube URL or search term")
async def play(interaction: discord.Interaction, url: str):
    # Check if guild is regulated
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    # Check if user is in a voice channel
    if not interaction.user.voice:
        await interaction.response.send_message('❌ You need to be in a voice channel!', ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    voice_channel = interaction.user.voice.channel
    guild = interaction.guild

    # Connect to voice channel if not already connected
    if not guild.voice_client:
        await voice_channel.connect(self_deaf=True)
    elif guild.voice_client.channel != voice_channel:
        await guild.voice_client.move_to(voice_channel)

    # Ensure bot is deafened for privacy
    await guild.change_voice_state(channel=guild.voice_client.channel, self_deaf=True)

    try:
        # Get song info
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if 'entries' in data:
            # Playlist
            entries = data['entries']
            queue = get_queue(guild.id)

            for entry in entries:
                if entry:  # Skip None entries
                    queue.append({
                        'url': entry['webpage_url'],
                        'title': entry['title']
                    })

            await interaction.followup.send(f'➕ Added {len(entries)} songs to the queue!')
        else:
            # Single song
            queue = get_queue(guild.id)
            queue.append({
                'url': data['webpage_url'],
                'title': data['title']
            })
            await interaction.followup.send(f'➕ Added to queue: **{data["title"]}**')

        # Start playing if nothing is playing
        if not guild.voice_client.is_playing():
            await play_next(guild)

    except Exception as e:
        await interaction.followup.send(f'❌ Error: {str(e)}')
        print(f'Error in play command: {e}')


class QueueView(discord.ui.View):
    def __init__(self, guild, queue_list, currently_playing_song, nonstop_mode):
        super().__init__(timeout=180)
        self.guild = guild
        self.queue_list = queue_list
        self.currently_playing_song = currently_playing_song
        self.nonstop_mode = nonstop_mode
        self.current_page = 0
        self.max_page = (len(queue_list) - 1) // 10 if len(queue_list) > 0 else 0

    def create_embed(self):
        embed = discord.Embed(title="🎵 Current Queue", color=0x2196F3)

        if self.currently_playing_song:
            embed.add_field(name="▶️ Now Playing", value=self.currently_playing_song['title'], inline=False)

        start_idx = self.current_page * 10
        end_idx = min(start_idx + 10, len(self.queue_list))

        if start_idx < len(self.queue_list):
            queue_text = ""
            for i in range(start_idx, end_idx):
                queue_text += f"`{i + 1}.` {self.queue_list[i]['title']}\n"

            embed.add_field(name=f"📋 Queue (Page {self.current_page + 1}/{self.max_page + 1})", value=queue_text, inline=False)

        embed.set_footer(text=f"Total songs: {len(self.queue_list)}" + (" | 🔀 NonStopPop Mode Active" if self.nonstop_mode else ""))

        return embed

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_page:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()


@bot.tree.command(name="queue", description="Show the current queue")
async def queue(interaction: discord.Interaction):
    # Check if guild is regulated
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    guild = interaction.guild
    queue_list = get_queue(guild.id)
    currently_playing_song = currently_playing.get(guild.id)
    nonstop_mode = nonstop_pop_mode.get(guild.id, False)

    if len(queue_list) == 0 and not currently_playing_song:
        embed = discord.Embed(title="🎵 Queue", description="📭 Queue is empty!", color=0x2196F3)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if len(queue_list) == 0 and currently_playing_song:
        # Only show currently playing, no queue
        embed = discord.Embed(title="🎵 Current Queue", color=0x2196F3)
        embed.add_field(name="▶️ Now Playing", value=currently_playing_song['title'], inline=False)
        embed.set_footer(text="No songs in queue" + (" | 🔀 NonStopPop Mode Active" if nonstop_mode else ""))
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    view = QueueView(guild, queue_list, currently_playing_song, nonstop_mode)
    embed = view.create_embed()

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="nonstoppop", description="Start or stop NonStopPop FM playlist (can take a minute to load all songs)")
@app_commands.describe(action="Start or Stop NonStopPop mode")
@app_commands.choices(action=[
    app_commands.Choice(name="Start", value="start"),
    app_commands.Choice(name="Stop", value="stop")
])
async def nonstoppop(interaction: discord.Interaction, action: app_commands.Choice[str]):
    # Check if guild is regulated
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    # Check if user is in a voice channel
    if not interaction.user.voice:
        await interaction.response.send_message('❌ You need to be in a voice channel!', ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    voice_channel = interaction.user.voice.channel

    if action.value == "start":
        # Connect to voice channel
        if not guild.voice_client:
            await voice_channel.connect(self_deaf=True)
        elif guild.voice_client.channel != voice_channel:
            await guild.voice_client.move_to(voice_channel)

        # Ensure bot is deafened for privacy
        await guild.change_voice_state(channel=guild.voice_client.channel, self_deaf=True)

        # Stop current playback
        if guild.voice_client.is_playing():
            guild.voice_client.stop()

        # Clear queue
        music_queues[guild.id] = []
        nonstop_pop_mode[guild.id] = True

        try:
            await interaction.followup.send('📻 **Loading NonStopPop FM playlist...**\n⏳ This can take a minute to load all songs, please wait...')

            # Load playlist
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(NONSTOP_POP_PLAYLIST, download=False))

            if 'entries' in data:
                entries = [e for e in data['entries'] if e]  # Filter out None

                # Shuffle the playlist
                random.shuffle(entries)

                # Add to queue
                queue = get_queue(guild.id)
                for entry in entries:
                    queue.append({
                        'url': entry['webpage_url'],
                        'title': entry['title']
                    })

                await interaction.edit_original_response(content=f'🔀 **NonStopPop FM Started!**\n📻 Loaded and shuffled {len(entries)} songs!')

                # Start playing
                await play_next(guild)
            else:
                await interaction.followup.send('❌ Failed to load playlist')
                nonstop_pop_mode[guild.id] = False

        except Exception as e:
            await interaction.followup.send(f'❌ Error loading playlist: {str(e)}')
            print(f'NonStopPop error: {e}')
            nonstop_pop_mode[guild.id] = False

    elif action.value == "stop":
        # Stop NonStopPop mode
        if guild.voice_client and guild.voice_client.is_playing():
            guild.voice_client.stop()

        # Clear queue
        music_queues[guild.id] = []
        nonstop_pop_mode[guild.id] = False

        await interaction.followup.send('⏹️ **NonStopPop FM Stopped!**\nQueue cleared.')


@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    # Check if guild is regulated
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    guild = interaction.guild

    if not guild.voice_client or not guild.voice_client.is_playing():
        await interaction.response.send_message('❌ Nothing is playing right now!', ephemeral=True)
        return

    # Check if there are more songs in the queue
    queue = get_queue(guild.id)
    if len(queue) == 0:
        await interaction.response.send_message('❌ There are no other queued songs!', ephemeral=True)
        return

    # Skip current song
    guild.voice_client.stop()
    await interaction.response.send_message('⏭️ Skipped!', ephemeral=True)


@bot.tree.command(name="pause", description="Pause or resume playback")
async def pause(interaction: discord.Interaction):
    # Check if guild is regulated
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    guild = interaction.guild

    if not guild.voice_client:
        await interaction.response.send_message('❌ Not connected to a voice channel!', ephemeral=True)
        return

    if guild.voice_client.is_playing():
        guild.voice_client.pause()
        manual_pause[guild.id] = True  # Mark as manually paused
        print("Playback paused manually")
        await interaction.response.send_message('⏸️ Paused!', ephemeral=True)
    elif guild.voice_client.is_paused():
        guild.voice_client.resume()
        manual_pause[guild.id] = False  # Clear manual pause flag
        print("Playback resumed manually")
        await interaction.response.send_message('▶️ Resumed!', ephemeral=True)
    else:
        await interaction.response.send_message('❌ Nothing is playing right now!', ephemeral=True)


@bot.tree.command(name="resume", description="Resume playback if paused")
async def resume(interaction: discord.Interaction):
    # Check if guild is regulated
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    guild = interaction.guild

    if not guild.voice_client:
        await interaction.response.send_message('❌ Not connected to a voice channel!', ephemeral=True)
        return

    if guild.voice_client.is_paused():
        guild.voice_client.resume()
        manual_pause[guild.id] = False  # Clear manual pause flag
        print("Playback resumed manually")
        await interaction.response.send_message('▶️ Resumed!', ephemeral=True)
    elif guild.voice_client.is_playing():
        await interaction.response.send_message('▶️ Already playing!', ephemeral=True)
    else:
        await interaction.response.send_message('❌ Nothing is paused right now!', ephemeral=True)


@bot.tree.command(name="previous", description="Play the previous song")
async def previous(interaction: discord.Interaction):
    # Check if guild is regulated
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    guild = interaction.guild

    if guild.id not in previous_songs or len(previous_songs[guild.id]) == 0:
        await interaction.response.send_message('❌ No previous songs in history!', ephemeral=True)
        return

    if not guild.voice_client:
        await interaction.response.send_message('❌ Not connected to a voice channel!', ephemeral=True)
        return

    # Get the last previous song
    prev_song = previous_songs[guild.id].pop()

    # Add current song back to front of queue if there is one
    if guild.id in currently_playing and currently_playing[guild.id]:
        queue = get_queue(guild.id)
        queue.insert(0, currently_playing[guild.id])

    # Add previous song to front of queue
    queue = get_queue(guild.id)
    queue.insert(0, prev_song)

    # Stop current playback to trigger next song
    if guild.voice_client.is_playing():
        guild.voice_client.stop()

    await interaction.response.send_message(f'⏮️ Playing previous: **{prev_song["title"]}**', ephemeral=True)


@bot.tree.command(name="queueclear", description="Clear the entire queue")
async def queueclear(interaction: discord.Interaction):
    # Check if guild is regulated
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    guild = interaction.guild
    queue = get_queue(guild.id)

    if len(queue) == 0:
        await interaction.response.send_message('❌ Queue is already empty!', ephemeral=True)
        return

    queue_count = len(queue)
    music_queues[guild.id] = []

    if guild.id in nonstop_pop_mode:
        nonstop_pop_mode[guild.id] = False

    print(f"Queue cleared ({queue_count} songs removed)")
    await interaction.response.send_message(f'🗑️ **Queue cleared!** Removed {queue_count} song(s).', ephemeral=True)


@bot.tree.command(name="stop", description="Stop playback and leave the voice channel")
async def stop(interaction: discord.Interaction):
    # Check if guild is regulated
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    guild = interaction.guild

    if not guild.voice_client:
        await interaction.response.send_message('❌ Not connected to a voice channel!', ephemeral=True)
        return

    # Stop playback if playing
    if guild.voice_client.is_playing():
        guild.voice_client.stop()

    # Disconnect from voice channel
    await guild.voice_client.disconnect()

    # Clear all state
    if guild.id in music_queues:
        music_queues[guild.id] = []
    if guild.id in nonstop_pop_mode:
        nonstop_pop_mode[guild.id] = False
    if guild.id in currently_playing:
        currently_playing[guild.id] = None

    print("Bot stopped and disconnected from voice channel")
    await interaction.response.send_message('⏹️ **Stopped!** Left the voice channel.', ephemeral=True)


@bot.tree.command(name="help", description="Show all available commands and features")
async def help_command(interaction: discord.Interaction):
    """Display help information about all bot commands"""
    embed = discord.Embed(
        title="🎵 Discord Music Bot - Help",
        description="A feature-rich music bot with queue management and playlist support",
        color=discord.Color.blue()
    )

    # Playback commands
    embed.add_field(
        name="🎮 Playback Commands",
        value=(
            "`/play [url]` - Play music from YouTube\n"
            "`/pause` - Pause or resume playback\n"
            "`/skip` - Skip the current song\n"
            "`/previous` - Play the previous song\n"
            "`/stop` - Stop playback and disconnect"
        ),
        inline=False
    )

    # Queue commands
    embed.add_field(
        name="📋 Queue Management",
        value=(
            "`/queue` - View current queue with pagination\n"
            "`/queueclear` - Clear the entire queue"
        ),
        inline=False
    )

    # Playlist commands
    embed.add_field(
        name="🎶 Playlist Features",
        value="`/nonstoppop [start/stop]` - Shuffle playlist mode",
        inline=False
    )

    # Admin commands
    embed.add_field(
        name="🔧 Admin Commands",
        value="`/regulate` - Toggle owner-only mode (server owner only)",
        inline=False
    )

    # Smart features
    embed.add_field(
        name="✨ Smart Features",
        value=(
            "• Auto-pause when alone in voice channel\n"
            "• Auto-disconnect after 5 minutes alone\n"
            "• All responses are private (ephemeral)\n"
            "• Tracks last 10 songs for /previous command"
        ),
        inline=False
    )

    embed.set_footer(text="All commands are slash commands - start typing / to see them!")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="logs", description="View recent command history for this server")
@app_commands.describe(page="Page number (10 commands per page)")
async def logs_command(interaction: discord.Interaction, page: int = 1):
    """Display command log history with pagination"""
    guild_id = interaction.guild.id

    # Get logs for this guild
    if guild_id not in command_logs or len(command_logs[guild_id]) == 0:
        await interaction.response.send_message("📜 No command history found for this server yet.", ephemeral=True)
        return

    logs = command_logs[guild_id]
    total_logs = len(logs)
    logs_per_page = 10
    total_pages = (total_logs + logs_per_page - 1) // logs_per_page  # Ceiling division

    # Validate page number
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    # Calculate slice indices
    start_idx = (page - 1) * logs_per_page
    end_idx = min(start_idx + logs_per_page, total_logs)
    page_logs = logs[start_idx:end_idx]

    # Build embed
    embed = discord.Embed(
        title=f"📜 Command History - Page {page}/{total_pages}",
        description=f"Showing {len(page_logs)} of {total_logs} commands",
        color=discord.Color.blue()
    )

    for log_entry in page_logs:
        command_text = f"`/{log_entry['command']}`"
        if log_entry['details']:
            command_text += f" - {log_entry['details']}"

        embed.add_field(
            name=f"{log_entry['timestamp']} - {log_entry['user']}",
            value=command_text,
            inline=False
        )

    embed.set_footer(text=f"Use /logs [page] to view other pages • Max 50 commands saved")

    await interaction.response.send_message(embed=embed, ephemeral=True)


async def regulate_check(interaction: discord.Interaction) -> bool:
    """Check if user is the server owner"""
    return interaction.user.id == interaction.guild.owner_id


@bot.tree.command(name="regulate", description="Toggle regulated mode (owner only)")
@app_commands.check(regulate_check)
async def regulate(interaction: discord.Interaction):
    """Toggle regulated mode (owner only)"""
    guild_id = interaction.guild.id

    if guild_id not in regulated_mode or not regulated_mode[guild_id]:
        regulated_mode[guild_id] = True
        print(f"Regulated mode enabled for guild: {interaction.guild.name}")
        await interaction.response.send_message('🔒 **Regulated Mode Enabled!**\nOnly the server owner can use bot commands.', ephemeral=True)
    else:
        regulated_mode[guild_id] = False
        print(f"Regulated mode disabled for guild: {interaction.guild.name}")
        await interaction.response.send_message('🔓 **Regulated Mode Disabled!**\nEveryone can use bot commands again.', ephemeral=True)


# Run the bot
if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print('❌ ERROR: DISCORD_TOKEN not found in environment variables!')
        print('Please set DISCORD_TOKEN in your .env file')
        input('Press Enter to exit...')
        exit(1)

    bot.run(token)
