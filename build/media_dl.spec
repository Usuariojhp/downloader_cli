# -*- mode: python ; coding: utf-8 -*-

# SPECPATH apunta al directorio de este archivo, así que las rutas del proyecto
# se resuelven igual desde cualquier cwd.
import os

ROOT = os.path.dirname(SPECPATH)
ENTRY = os.path.join(ROOT, "src", "media_dl", "main.py")
SRC = os.path.join(ROOT, "src")

block_cipher = None

a = Analysis(
    [ENTRY],
    pathex=[SRC],
    binaries=[],
    datas=[],
    hiddenimports=[
        'rich',
        'yt_dlp',
        'pydantic',
        'typer',
        'media_dl.core.models',
        'media_dl.core.exceptions',
        'media_dl.core.extractors.ytdlp',
        'media_dl.core.extractors.tiktok_tikwn',
        'media_dl.core.extractors.spotify',
        'media_dl.core.extractors.soundcloud',
        'media_dl.core.strategies.aria2c',
        'media_dl.core.strategies.native',
        'media_dl.core.history.models',
        'media_dl.core.history.repository',
        'platformdirs',
        'pydantic_settings',
        'media_dl.ui.console',
        'media_dl.ui.theme',
        'media_dl.ui.menus',
        'media_dl.ui.tables',
        'media_dl.ui.prompts',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'cv2',
        'torch',
        'tensorflow',
        # Dependencias opcionales de yt-dlp que necesitan datos empaquetados
        'pykakasi',
        'secretstorage',
        'websockets',
        # NO excluir 'mutagen': yt-dlp lo necesita para los formatos de audio de
        # YouTube Music y sin él la descarga de Spotify falla con un falso
        # "The requested site is known to use DRM protection". Además media-dl
        # lo usa para incrustar la carátula.
    ],
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
    name='media-dl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)