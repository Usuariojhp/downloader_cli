"""Embed cover art into downloaded audio files.

yt-dlp's ``EmbedThumbnail`` only works when the media source itself carries an
attached picture. Audio pulled from YouTube Music usually does not, so
Spotify downloads ended up with no cover at all even though the extractor
already knew the album art URL. This module closes that gap.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_TIMEOUT = 15

_MP4_SUFFIXES = (".m4a", ".mp4", ".m4b")


def _fetch(image_url: str) -> bytes | None:
    """Download a cover image. Returns None instead of raising."""
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
    if not image_url or not path.exists():
        return False
    if has_cover(path):
        return True

    image = _fetch(image_url)
    if not image:
        return False

    suffix = path.suffix.lower()

    try:
        if suffix == ".mp3":
            # mutagen no marca reexportaciones explícitas, así que mypy estricto
            # se queja de APIC aunque exista en mutagen.id3.
            from mutagen.id3 import APIC, ID3  # type: ignore[attr-defined]

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
            return True

        if suffix in _MP4_SUFFIXES:
            from mutagen.mp4 import MP4, MP4Cover

            container: Any = MP4
            cover: Any = MP4Cover
            audio: Any = container(path)
            if audio.tags is None:
                audio.add_tags()
            audio.tags["covr"] = [cover(image, imageformat=cover.FORMAT_JPEG)]
            audio.save()
            return True
    except Exception:
        return False

    return False
