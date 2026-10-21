# -*- mode: python ; coding: utf-8 -*-

# SPECPATH apunta al directorio de este archivo, así que las rutas del proyecto
# se resuelven igual desde cualquier cwd.
import os

ROOT = os.path.dirname(SPECPATH)
ENTRY = os.path.join(ROOT, "src", "veluz", "main.py")
SRC = os.path.join(ROOT, "src")


def _pykakasi_data():
    """Todo lo que necesita spotdl: codigo, datos y submodulos.

    spotdl arrastra un arbol enorme de dependencias (spotapi, ytmusicapi,
    pymongo, curl_cffi...) y varias traen ficheros de datos que PyInstaller no
    detecta solo: sin ellos, 'import spotdl' o el formateador de titulos
    revientan con FileNotFoundError en tiempo de ejecucion. collect_all lo
    resuelve de una vez, en vez de ir scopando faltante por faltante.

    mutagen se recoge a proposito aunque su import sea estatico: es la
    dependencia de la caratula, y si se pierde, embed_cover se traga la
    excepcion y las descargas salen sin portada sin avisar de nada.
    """
    try:
        from PyInstaller.utils.hooks import collect_all
    except ImportError:
        return [], [], []

    datas, binaries, hiddenimports = [], [], []
    for paquete in ("spotdl", "pykakasi", "spotapi", "ytmusicapi", "mutagen"):
        try:
            d, b, h = collect_all(paquete)
        except Exception:
            continue
        datas += d
        binaries += b
        hiddenimports += h
    return datas, binaries, hiddenimports


_DATAS, _BINARIES, _SPOTIFY_IMPORTS = _pykakasi_data()

block_cipher = None

a = Analysis(
    [ENTRY],
    pathex=[SRC],
    binaries=_BINARIES,
    datas=_DATAS,
    hiddenimports=[
        'rich',
        'yt_dlp',
        'pydantic',
        'typer',
        'veluz.core.models',
        'veluz.core.exceptions',
        'veluz.core.extractors.ytdlp',
        'veluz.core.extractors.tiktok_tikwn',
        'veluz.core.extractors.spotify',
        'veluz.core.extractors.soundcloud',
        'veluz.core.strategies.aria2c',
        'veluz.core.strategies.native',
        'veluz.core.history.models',
        'veluz.core.history.repository',
        'platformdirs',
        'pydantic_settings',
        'veluz.ui.console',
        'veluz.ui.theme',
        'veluz.ui.menus',
        'veluz.ui.tables',
        'veluz.ui.prompts',
        *_SPOTIFY_IMPORTS,
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
        # Estas exclusiones sí son seguras: son dependencias opcionales de
        # yt-dlp que se descargan con datos aparte y que no usa veluz.
        'secretstorage',
        # NO excluir 'mutagen', 'websockets' ni 'pykakasi', por razones distintas:
        #
        # - mutagen: lo usa yt-dlp para los formatos de audio de YouTube
        #   Music, y veluz.core.cover para incrustar la portada. Sin él,
        #   Spotify muere con un falso "known to use DRM protection".
        # - websockets: lo importa spotdl, que es nuestro extra de Spotify.
        # - pykakasi: lo importa spotdl.utils.formatter, también arriba.
        #
        # Con cualquiera de los tres fuera, 'import spotdl' falla,
        # check_spotdl() devuelve False, el extractor de Spotify deja de
        # aceptar las URL y el encargo cae en el extractor genérico de
        # yt-dlp, que sí dice DRM (y esta vez con razón, porque la URL es
        # de Spotify).
        #
        # Estas cosas solo se rompen en el binario: con pip van bien, porque
        # ahí llega el paquete entero. tests/test_packaging.py vigila que no
        # se excluya ninguna dependencia declarada, y la CI ejecuta
        # 'doctor --strict' sobre el binario ya compilado.
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
    name='veluz',
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