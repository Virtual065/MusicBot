# PyInstaller spec file for Discord Music Bot
# This ensures all dependencies are properly included

import os
import sys

block_cipher = None

a = Analysis(
    ['bot_systray.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'discord',
        'discord.ext.commands',
        'discord.ext.tasks',
        'yt_dlp',
        'asyncio',
        'dotenv',
        'pystray',
        'PIL',
        'psutil',
        'tkinter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DiscordMusicBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
