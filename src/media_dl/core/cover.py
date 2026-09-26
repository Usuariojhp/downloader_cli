"""Embed cover art into downloaded audio files.

yt-dlp's ``EmbedThumbnail`` only works when the media source itself carries an
attached picture. Audio pulled from YouTube Music usually does not, so
Spotify downloads ended up with no cover at all even though the extractor
already knew the album art URL. This module closes that gap.
"""

from __future__ import annotations

import base64
import binascii
import os
import ssl
import sys
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


def _bundled_ca_file() -> str | None:
    """Return certifi's ``cacert.pem`` when running from a frozen bundle.

    PyInstaller sets ``SSL_CERT_FILE`` to certifi's ``cacert.pem`` in the
    bundle, but only ships certifi as data and does not import it. A plain
    ``urllib`` call then has no issuer certificate to validate against:

        CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate

    while every other download works, because yt-dlp and spotdl go through
    requests/httpx, which import certifi from the PYZ and get their own copy.
    That is why the audio arrived and the cover silently did not.
    """
    candidate = os.environ.get("SSL_CERT_FILE", "")
    if candidate and Path(candidate).is_file():
        return candidate
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None
    bundled = Path(meipass) / "certifi" / "cacert.pem"
    return str(bundled) if bundled.is_file() else None


def _fetch(image_url: str) -> tuple[bytes | None, str]:
    """Download a cover image, with the reason if it could not be fetched.

    Devolver solo los bytes hacia el fallo al `except` de urllib, que se
    tragaba el motivo. Con SSL eso es un agujero: 'no se pudo descargar la
    imagen' no dice si fue un 404, un certificado que no valida o la red.
    """
    if image_url.startswith("data:"):
        image = _decode_data_url(image_url)
        if image is None:
            return None, "data: URL de imagen no válida"
        return image, "ok"

    request = urllib.request.Request(image_url, headers={"User-Agent": "media-dl"})
    context = None
    ca_file = _bundled_ca_file()
    if ca_file:
        try:
            context = ssl.create_default_context(cafile=ca_file)
        except (OSError, ValueError):
            # Sin CA utilizable se va con la que traiga el sistema, que es lo
            # que se ha usado siempre.
            context = None
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT, context=context) as response:
            return response.read(), "ok"
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code} al pedir la imagen"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # ssl.SSLError y SSLCertVerificationError entran por aquí como OSError,
        # que es justo el caso que hay que poder leer en el aviso.
        return None, f"{type(exc).__name__}: {exc}"


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

    image, fetch_reason = _fetch(image_url)
    if not image:
        return False, fetch_reason

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


def ca_status() -> tuple[bool, str]:
    """Return (ok, detail) indicating if this process can verify HTTPS certs.

    No hace un handshake real (requeriría red). En su lugar comprueba que
    exista ALGUNA fuente de CA en el filesystem:

    - Un certifi empaquetado en el bundle (PyInstaller pone SSL_CERT_FILE)
    - La variable SSL_CERT_FILE apuntando a un archivo existente
    - Las rutas por defecto de OpenSSL (cafile o capath existentes)

    Si NINGUNA existe, `urllib.request.urlopen` fallará con
    CERTIFICATE_VERIFY_FAILED en cualquier HTTPS. Eso es un defecto real
    del empaquetado, no un capricho de red.

    Contar certificados con create_default_context() NO sirve: devuelve 0
    incluso en sistemas donde HTTPS funciona (OpenSSL puebla el almacén
    de forma perezosa).
    """
    # 1) Bundled certifi inside the frozen app
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "certifi" / "cacert.pem"
        if bundled.is_file():
            return True, f"certifi empaquetado ({bundled.name})"

    # 2) Explicit SSL_CERT_FILE env var
    env_cert = os.environ.get("SSL_CERT_FILE", "")
    if env_cert and Path(env_cert).is_file():
        return True, f"SSL_CERT_FILE={env_cert}"

    # 3) System default verify paths
    verify_paths = ssl.get_default_verify_paths()
    cafile = getattr(verify_paths, "openssl_cafile", "")
    capath = getattr(verify_paths, "openssl_capath", "")
    if cafile and Path(cafile).is_file():
        return True, f"CA del sistema: {Path(cafile).name}"
    if capath and Path(capath).is_dir():
        return True, f"CA dir del sistema: {Path(capath).name}"

    return False, "NINGUNA fuente de CA encontrada: HTTPS por urllib fallará"


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
