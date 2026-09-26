"""Embed cover art into downloaded audio files.

yt-dlp's ``EmbedThumbnail`` only works when the media source itself carries an
attached picture. Audio pulled from YouTube Music usually does not, so
Spotify downloads ended up with no cover at all even though the extractor
already knew the album art URL. This module closes that gap.
"""

from __future__ import annotations

import base64
import binascii
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_TIMEOUT = 15

_MP4_SUFFIXES = (".m4a", ".mp4", ".m4b")

_MAX_INLINE_IMAGE = 4 * 1024 * 1024

# JPEG de 1x1 en blanco, en base64. Sirve para probar la incrustacion sin
# red, que es como se comprueba dentro del binario.
_TINY_JPEG_DATA_URL = (
    "data:image/jpeg;base64,"
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)


def _decode_data_url(image_url: str) -> bytes | None:
    """Decode a ``data:image/...;base64,...`` URL, or None if it is not one.

    Se admite para que ``embed_cover`` se pueda probar sin red: la
    incrustacion es justo lo que hay que verificar en el binario, y atar la
    prueba a un CDN hace que valga lo que valga la conexion ese dia.
    """
    header, _, payload = image_url.partition(",")
    if not header.startswith("data:image/") or not payload:
        return None
    if ";base64" not in header:
        return None
    if len(payload) > _MAX_INLINE_IMAGE:
        return None
    try:
        return base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error):
        return None


def _fetch(image_url: str) -> bytes | None:
    """Download a cover image. Returns None instead of raising."""
    if image_url.startswith("data:"):
        return _decode_data_url(image_url)
    request = urllib.request.Request(image_url, headers={"User-Agent": "media-dl"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return response.read()  # type: ignore[no-any-return]
    except (urllib.error.URLError, OSError, ValueError):
        return None


def has_cover(path: Path) -> bool:
    """Return True if the file already carries embedded cover art."""
    suffix = path.suffix.lower()

    if suffix == ".mp3":
        try:
            from mutagen.id3 import ID3

            load: Any = ID3
            return any(key.startswith("APIC") for key in load(path))
        except Exception:
            return False

    if suffix in _MP4_SUFFIXES:
        try:
            from mutagen.mp4 import MP4

            container: Any = MP4
            tags: Any = container(path).tags
            return bool(tags) and bool(tags.get("covr"))
        except Exception:
            return False

    return False


def embed_cover(path: Path, image_url: str | None) -> bool:
    """Embed ``image_url`` as cover art. Never raises.

    Returns True only if the file ends up with a cover. A missing mutagen, an
    unsupported container or a dead image URL all return False so that a
    download is never reported as failed just because artwork did not stick.
    """
    ok, _reason = explain_embed_cover(path, image_url)
    return ok


def explain_embed_cover(path: Path, image_url: str | None) -> tuple[bool, str]:
    """``embed_cover`` pero diciendo por qué no, en vez de tragárselo.

    Devolver solo un booleano fue justo lo que dejó invisible un bug de
    empaquetado entero: mutagen desapareció del binario, ``embed_cover``
    devolvía False con la boca cerrada y las descargas salían sin portada sin
    que nadie se enterara, ni la CI ni el usuario. Quien quiera el detalle
    (doctor) lo pide aquí.
    """
    if not image_url:
        return False, "sin URL de portada"
    if not path.exists():
        return False, "el fichero no existe"
    if has_cover(path):
        return True, "ya tenía portada"

    image = _fetch(image_url)
    if not image:
        return False, "no se pudo descargar la imagen"

    suffix = path.suffix.lower()

    try:
        if suffix == ".mp3":
            # Import estatico a proposito: PyInstaller solo ve las sentencias
            # de import, no los importlib.import_module, asi que un import
            # dinamico hace que mutagen no entre en el binario y las
            # portadas dejen de incrustarse sin que nada avise.
            # El suelo de mutagen es 1.48, donde APIC ya viene declarado
            # como reexportacion y mypy no necesita un 'type: ignore'.
            from mutagen.id3 import APIC, ID3

            load: Any = ID3
            new_tags: Any = ID3
            frame: Any = APIC
            try:
                tags = load(path)
            except Exception:
                # Un MP3 recién descargado puede no traer cabecera ID3 todavía;
                # se crea una etiqueta nueva y se le pega la portada.
                tags = new_tags()
            tags.delall("APIC")
            tags.add(frame(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=image))
            tags.save(path)
            return True, "portada incrustada"

        if suffix in _MP4_SUFFIXES:
            from mutagen.mp4 import MP4, MP4Cover

            container: Any = MP4
            cover: Any = MP4Cover
            audio: Any = container(path)
            if audio.tags is None:
                audio.add_tags()
            audio.tags["covr"] = [cover(image, imageformat=cover.FORMAT_JPEG)]
            audio.save()
            return True, "portada incrustada"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    return False, f"contenedor no soportado ({suffix or 'sin extensión'})"


def self_test() -> tuple[bool, str]:
    """Check that cover embedding really works here, with no network involved.

    Se usa en ``doctor`` porque hay fallos que solo se ven dentro del
    empaquetado: mutagen ausente, mutagen que no puede escribir, un binario
    donde el import se perdio. Todo eso aqui sale bien o mal de verdad, en vez
    de deducirlo de una tabla de versiones.
    """
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "self_test.mp3"
        # Frame MPEG minimo: a embed_cover solo le hace falta que exista.
        probe.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 413)
        return explain_embed_cover(probe, _TINY_JPEG_DATA_URL)
