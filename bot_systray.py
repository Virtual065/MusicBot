import discord
from discord import app_commands
from discord.ext import commands, tasks
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv
import pystray
from PIL import Image, ImageDraw
import threading
import psutil
from datetime import datetime
import logging
import sys
import random
import tkinter as tk
from tkinter import messagebox

# Setup logging to file
log_file = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'musicbot.log')
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Bot starting... Log file: {log_file}")

# Configuration management
def load_config():
    """Load configuration from Info.txt or .env"""
    config_file = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'Info.txt')

    if os.path.exists(config_file):
        logger.info("Loading configuration from Info.txt")
        config = {}
        with open(config_file, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    config[key] = value
        return config.get('DISCORD_TOKEN')
    else:
        # Try .env file as fallback
        load_dotenv()
        token = os.getenv('DISCORD_TOKEN')
        if token:
            logger.info("Loaded token from .env file")
            return token

        # No config found - prompt user
        logger.info("No configuration found. Prompting user...")
        return prompt_for_config(config_file)


def prompt_for_config(config_file):
    """Prompt user for Discord token via GUI"""
    root = tk.Tk()
    root.title("Discord Music Bot - First Time Setup")
    root.geometry("500x250")
    root.resizable(False, False)

    # Title
    title_label = tk.Label(root, text="Discord Music Bot Setup", font=("Arial", 16, "bold"))
    title_label.pack(pady=20)

    # Instructions
    info_label = tk.Label(root, text="Please enter your Discord Bot Token:", font=("Arial", 10))
    info_label.pack()

    # Token entry
    token_var = tk.StringVar()
    token_entry = tk.Entry(root, textvariable=token_var, width=50, show="*")
    token_entry.pack(pady=10)

    # Show/hide password
    def toggle_password():
        if token_entry.cget('show') == '*':
            token_entry.config(show='')
            show_btn.config(text='Hide Token')
        else:
            token_entry.config(show='*')
            show_btn.config(text='Show Token')

    show_btn = tk.Button(root, text="Show Token", command=toggle_password)
    show_btn.pack(pady=5)

    result = {'token': None}

    def save_and_continue():
        token = token_var.get().strip()
        if not token:
            messagebox.showerror("Error", "Please enter a valid Discord token!")
            return

        # Save to Info.txt
        with open(config_file, 'w') as f:
            f.write(f"DISCORD_TOKEN={token}\n")

        result['token'] = token
        logger.info("Configuration saved to Info.txt")
        root.destroy()

    # Save button
    save_btn = tk.Button(root, text="Save and Start Bot", command=save_and_continue, bg="#5865F2", fg="white", font=("Arial", 10, "bold"), width=20)
    save_btn.pack(pady=20)

    # Help link
    help_label = tk.Label(root, text="Need help? Visit: https://discord.com/developers/applications", fg="blue", cursor="hand2")
    help_label.pack()

    root.mainloop()

    return result['token']


# Load configuration
logger.info("Loading bot configuration...")
DISCORD_TOKEN = load_config()

if not DISCORD_TOKEN:
    logger.error("No Discord token provided. Exiting...")
    messagebox.showerror("Error", "Failed to get Discord token. Bot will now exit.")
    sys.exit(1)

logger.info("Configuration loaded successfully")

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
currently_playing = {}
previous_songs = {}
regulated_mode = {}

# Playlist URL
NONSTOP_POP_PLAYLIST = "https://youtube.com/playlist?list=PLgbI0QcBNn5isOvlIN0rRK9Y6bSQdheii&si=Cqb7oJDTsYBDHXLz"

# yt-dlp options
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
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
            return data['entries']

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)


# Global variables for system tray
icon = None
bot_status = "Starting..."
start_time = datetime.now()


def get_queue(guild_id):
    """Get or create queue for a guild"""
    if guild_id not in music_queues:
        music_queues[guild_id] = []
    return music_queues[guild_id]


async def play_next(guild, skip_previous_tracking=False):
    """Play the next song in the queue"""
    global bot_status
    queue = get_queue(guild.id)

    if len(queue) == 0:
        last_activity[guild.id] = datetime.now()
        currently_playing[guild.id] = None
        bot_status = "Online"
        return

    voice_client = guild.voice_client
    if not voice_client:
        return

    next_song = queue.pop(0)

    # Track previous song if not skipping
    if not skip_previous_tracking and guild.id in currently_playing and currently_playing[guild.id]:
        if guild.id not in previous_songs:
            previous_songs[guild.id] = []
        previous_songs[guild.id].append(currently_playing[guild.id])
        if len(previous_songs[guild.id]) > 10:
            previous_songs[guild.id].pop(0)

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(next_song['url'], download=False))

        if 'entries' in data:
            data = data['entries'][0]

        player = YTDLSource(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), data=data)

        currently_playing[guild.id] = next_song

        def after_playing(error):
            if error:
                logger.error(f'Player error: {error}')
            asyncio.run_coroutine_threadsafe(play_next(guild), bot.loop)

        voice_client.play(player, after=after_playing)
        last_activity[guild.id] = datetime.now()

        bot_status = "Playing music"

        if guild.id in nonstop_pop_mode and nonstop_pop_mode[guild.id]:
            logger.info(f"[NonStopPop] Now playing: {player.title}")
        else:
            logger.info(f"Now playing: {player.title}")

    except Exception as e:
        logger.error(f'Error playing next song: {e}')
        await play_next(guild)


@tasks.loop(seconds=30)
async def check_empty_vc():
    """Check for empty voice channels - pause immediately, disconnect after 5 minutes"""
    global bot_status
    current_time = datetime.now()

    for guild in bot.guilds:
        voice_client = guild.voice_client

        if voice_client and voice_client.channel:
            members = [m for m in voice_client.channel.members if not m.bot]

            if len(members) == 0:
                # Pause immediately if playing and not already paused
                if voice_client.is_playing():
                    voice_client.pause()
                    logger.info(f"Paused playback in {guild.name} - VC is empty")
                    bot_status = "Paused (empty VC)"

                if guild.id in last_activity:
                    time_diff = (current_time - last_activity[guild.id]).total_seconds()

                    if time_diff >= 300:
                        logger.info(f"Disconnecting from {guild.name} - VC empty for 5 minutes")
                        await voice_client.disconnect()
                        if guild.id in music_queues:
                            music_queues[guild.id] = []
                        if guild.id in nonstop_pop_mode:
                            nonstop_pop_mode[guild.id] = False
                        if guild.id in currently_playing:
                            currently_playing[guild.id] = None
                        bot_status = "Online"
                else:
                    last_activity[guild.id] = current_time
            else:
                # Resume if paused when people rejoin
                if voice_client.is_paused():
                    voice_client.resume()
                    logger.info(f"Resumed playback in {guild.name} - users rejoined")
                    bot_status = "Playing music"

                last_activity[guild.id] = current_time


def create_image():
    """Create a simple icon for the system tray"""
    width = 64
    height = 64
    # Create a red square
    image = Image.new('RGB', (width, height), color=(255, 0, 0))
    return image


def get_resource_usage():
    """Get current resource usage"""
    process = psutil.Process(os.getpid())
    cpu_percent = process.cpu_percent(interval=0.1)
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024

    uptime = datetime.now() - start_time
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    return {
        'cpu': cpu_percent,
        'memory': memory_mb,
        'uptime': f"{hours}h {minutes}m {seconds}s"
    }


def update_tooltip(icon_ref):
    """Update the tooltip with bot name"""
    if icon_ref:
        icon_ref.title = "Discord Music Bot"


def setup_system_tray():
    """Setup system tray icon"""
    global icon

    def on_quit(icon_ref, item):
        icon_ref.stop()
        asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)

    def show_stats(icon_ref, item):
        def create_stats_window():
            # Create stats window
            stats_window = tk.Tk()
            stats_window.title("Discord Music Bot - Stats")
            stats_window.geometry("400x250")
            stats_window.resizable(False, False)

            # Create labels for stats
            title_label = tk.Label(stats_window, text="Discord Music Bot Statistics", font=("Arial", 14, "bold"))
            title_label.pack(pady=10)

            separator = tk.Label(stats_window, text="=" * 40)
            separator.pack()

            stats_frame = tk.Frame(stats_window)
            stats_frame.pack(pady=20)

            status_label = tk.Label(stats_frame, text="", font=("Arial", 10), anchor="w")
            status_label.pack(fill="x", padx=20)

            cpu_label = tk.Label(stats_frame, text="", font=("Arial", 10), anchor="w")
            cpu_label.pack(fill="x", padx=20)

            memory_label = tk.Label(stats_frame, text="", font=("Arial", 10), anchor="w")
            memory_label.pack(fill="x", padx=20)

            uptime_label = tk.Label(stats_frame, text="", font=("Arial", 10), anchor="w")
            uptime_label.pack(fill="x", padx=20)

            def update_stats():
                stats = get_resource_usage()
                status_label.config(text=f"Status: {bot_status}")
                cpu_label.config(text=f"CPU Usage: {stats['cpu']:.1f}%")
                memory_label.config(text=f"Memory Usage: {stats['memory']:.1f} MB")
                uptime_label.config(text=f"Uptime: {stats['uptime']}")
                stats_window.after(1000, update_stats)  # Update every second

            # Close button
            close_btn = tk.Button(stats_window, text="Close", command=stats_window.destroy, width=10)
            close_btn.pack(pady=10)

            update_stats()
            stats_window.mainloop()

        # Run in a separate thread to avoid blocking
        threading.Thread(target=create_stats_window, daemon=True).start()

    menu = pystray.Menu(
        pystray.MenuItem("Show Stats", show_stats),
        pystray.MenuItem("Quit", on_quit)
    )

    icon = pystray.Icon("Discord Music Bot", create_image(), menu=menu)

    def tooltip_updater():
        while icon.visible:
            update_tooltip(icon)
            asyncio.run_coroutine_threadsafe(asyncio.sleep(2), bot.loop)
            threading.Event().wait(2)

    tooltip_thread = threading.Thread(target=tooltip_updater, daemon=True)
    tooltip_thread.start()

    icon.run()


@bot.event
async def on_ready():
    global bot_status
    bot_status = "Online"
    logger.info(f'Bot is ready! Logged in as {bot.user}')
    logger.info(f'Bot ID: {bot.user.id}')
    logger.info('Syncing slash commands...')

    try:
        synced = await bot.tree.sync()
        logger.info(f'Successfully synced {len(synced)} slash command(s)')
        for cmd in synced:
            logger.info(f'  - /{cmd.name}')
    except Exception as e:
        logger.error(f'Error syncing commands: {e}', exc_info=True)

    check_empty_vc.start()
    logger.info('Running in system tray...')
    logger.info('Right-click the tray icon to see options')


@bot.tree.command(name="play", description="Add a song to the queue")
@app_commands.describe(url="YouTube URL or search term")
async def play(interaction: discord.Interaction, url: str):
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    logger.info(f"Play command received. URL: {url}")

    if not interaction.user.voice:
        await interaction.response.send_message('❌ You need to be in a voice channel!', ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    voice_channel = interaction.user.voice.channel
    guild = interaction.guild

    logger.info(f"User is in voice channel: {voice_channel.name}")

    if not guild.voice_client:
        logger.info(f"Connecting to voice channel: {voice_channel.name}")
        await voice_channel.connect(self_deaf=True)
    elif guild.voice_client.channel != voice_channel:
        logger.info(f"Moving to voice channel: {voice_channel.name}")
        await guild.voice_client.move_to(voice_channel)

    # Ensure bot is deafened for privacy
    await guild.change_voice_state(channel=guild.voice_client.channel, self_deaf=True)

    try:
        logger.info(f"Attempting to load audio from: {url}")
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if 'entries' in data:
            entries = data['entries']
            queue = get_queue(guild.id)

            for entry in entries:
                if entry:
                    queue.append({
                        'url': entry['webpage_url'],
                        'title': entry['title']
                    })

            logger.info(f"Added {len(entries)} songs to queue")
            await interaction.followup.send(f'➕ Added {len(entries)} songs to the queue!')
        else:
            queue = get_queue(guild.id)
            queue.append({
                'url': data['webpage_url'],
                'title': data['title']
            })
            logger.info(f"Added to queue: {data['title']}")
            await interaction.followup.send(f'➕ Added to queue: **{data["title"]}**')

        if not guild.voice_client.is_playing():
            await play_next(guild)

    except Exception as e:
        logger.error(f'Error in play command: {e}', exc_info=True)
        await interaction.followup.send(f'❌ Error: {str(e)}')


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
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    if not interaction.user.voice:
        await interaction.response.send_message('❌ You need to be in a voice channel!', ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    voice_channel = interaction.user.voice.channel

    if action.value == "start":
        if not guild.voice_client:
            await voice_channel.connect(self_deaf=True)
        elif guild.voice_client.channel != voice_channel:
            await guild.voice_client.move_to(voice_channel)

        # Ensure bot is deafened for privacy
        await guild.change_voice_state(channel=guild.voice_client.channel, self_deaf=True)

        if guild.voice_client.is_playing():
            guild.voice_client.stop()

        music_queues[guild.id] = []
        nonstop_pop_mode[guild.id] = True

        try:
            await interaction.followup.send('📻 **Loading NonStopPop FM playlist...**\n⏳ This can take a minute to load all songs, please wait...')
            logger.info("Loading NonStopPop FM playlist...")

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(NONSTOP_POP_PLAYLIST, download=False))

            if 'entries' in data:
                entries = [e for e in data['entries'] if e]
                random.shuffle(entries)

                queue = get_queue(guild.id)
                for entry in entries:
                    queue.append({
                        'url': entry['webpage_url'],
                        'title': entry['title']
                    })

                logger.info(f"NonStopPop FM: Loaded and shuffled {len(entries)} songs")
                await interaction.edit_original_response(content=f'🔀 **NonStopPop FM Started!**\n📻 Loaded and shuffled {len(entries)} songs!')

                await play_next(guild)
            else:
                await interaction.followup.send('❌ Failed to load playlist')
                nonstop_pop_mode[guild.id] = False

        except Exception as e:
            logger.error(f'NonStopPop error: {e}', exc_info=True)
            await interaction.followup.send(f'❌ Error loading playlist: {str(e)}')
            nonstop_pop_mode[guild.id] = False

    elif action.value == "stop":
        if guild.voice_client and guild.voice_client.is_playing():
            guild.voice_client.stop()

        music_queues[guild.id] = []
        nonstop_pop_mode[guild.id] = False

        logger.info("NonStopPop FM stopped")
        await interaction.followup.send('⏹️ **NonStopPop FM Stopped!**\nQueue cleared.')


@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
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

    guild.voice_client.stop()
    logger.info("Song skipped")
    await interaction.response.send_message('⏭️ Skipped!', ephemeral=True)


@bot.tree.command(name="pause", description="Pause or resume playback")
async def pause(interaction: discord.Interaction):
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
        logger.info("Playback paused")
        await interaction.response.send_message('⏸️ Paused!', ephemeral=True)
    elif guild.voice_client.is_paused():
        guild.voice_client.resume()
        logger.info("Playback resumed")
        await interaction.response.send_message('▶️ Resumed!', ephemeral=True)
    else:
        await interaction.response.send_message('❌ Nothing is playing right now!', ephemeral=True)


@bot.tree.command(name="previous", description="Play the previous song")
async def previous(interaction: discord.Interaction):
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

    prev_song = previous_songs[guild.id].pop()

    if guild.id in currently_playing and currently_playing[guild.id]:
        queue = get_queue(guild.id)
        queue.insert(0, currently_playing[guild.id])

    queue = get_queue(guild.id)
    queue.insert(0, prev_song)

    if guild.voice_client.is_playing():
        guild.voice_client.stop()

    logger.info(f"Playing previous song: {prev_song['title']}")
    await interaction.response.send_message(f'⏮️ Playing previous: **{prev_song["title"]}**', ephemeral=True)


@bot.tree.command(name="queueclear", description="Clear the entire queue")
async def queueclear(interaction: discord.Interaction):
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

    logger.info(f"Queue cleared ({queue_count} songs removed)")
    await interaction.response.send_message(f'🗑️ **Queue cleared!** Removed {queue_count} song(s).', ephemeral=True)


@bot.tree.command(name="stop", description="Stop playback and leave the voice channel")
async def stop(interaction: discord.Interaction):
    if interaction.guild.id in regulated_mode and regulated_mode[interaction.guild.id]:
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message('🔒 Bot is in regulated mode. Only the server owner can use commands.', ephemeral=True)
            return

    guild = interaction.guild

    if not guild.voice_client:
        await interaction.response.send_message('❌ Not connected to a voice channel!', ephemeral=True)
        return

    if guild.voice_client.is_playing():
        guild.voice_client.stop()

    await guild.voice_client.disconnect()

    if guild.id in music_queues:
        music_queues[guild.id] = []
    if guild.id in nonstop_pop_mode:
        nonstop_pop_mode[guild.id] = False
    if guild.id in currently_playing:
        currently_playing[guild.id] = None

    logger.info("Bot stopped and disconnected from voice channel")
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
        logger.info(f"Regulated mode enabled for guild: {interaction.guild.name}")
        await interaction.response.send_message('🔒 **Regulated Mode Enabled!**\nOnly the server owner can use bot commands.', ephemeral=True)
    else:
        regulated_mode[guild_id] = False
        logger.info(f"Regulated mode disabled for guild: {interaction.guild.name}")
        await interaction.response.send_message('🔓 **Regulated Mode Disabled!**\nEveryone can use bot commands again.', ephemeral=True)


def run_bot():
    """Run the Discord bot"""
    logger.info("run_bot() called")
    logger.info("Starting bot with token...")
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f'Error running bot: {e}', exc_info=True)
        print(f'❌ Error running bot: {e}')
        input('Press Enter to exit...')


# Run the bot
if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    setup_system_tray()
