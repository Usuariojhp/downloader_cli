"""Tests for cover art embedding."""

from __future__ import annotations

import os
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from unittest.mock import patch

import certifi

from media_dl.core import cover as cover_module
from media_dl.core.cover import (
    embed_cover,
    explain_embed_cover,
    has_cover,
    self_test,
)

_TINY_B64 = cover_module._TINY_JPEG_DATA_URL.split(",", 1)[1]


def _png(color: tuple[int, int, int] = (200, 30, 30)) -> bytes:
    """Build a tiny valid PNG so mutagen stores real bytes."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + bytes((*color, 255)) for _ in range(1))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class _FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _mp3(path: Path) -> Path:
    """Write a file mutagen will accept as an MP3."""
    path.write_bytes(b"\xff\xfb\x90\x64" + b"\x00" * 512)
    return path


class TestEmbedCoverMp3:
    def test_embeds_picture(self, temp_dir: Path) -> None:
        target = _mp3(temp_dir / "cancion.mp3")
        png = _png()

        with patch("media_dl.core.cover._fetch", return_value=(png, "ok")):
            assert embed_cover(target, "https://cdn.example/cover.png") is True

        assert has_cover(target) is True

        from mutagen.id3 import ID3

        frames = ID3(target).getall("APIC")
        assert frames[0].data == png

    def test_replaces_existing_picture(self, temp_dir: Path) -> None:
        target = _mp3(temp_dir / "cancion.mp3")

        with patch("media_dl.core.cover._fetch", return_value=(_png((1, 1, 1)), "ok")):
            embed_cover(target, "https://cdn.example/a.png")
        with patch("media_dl.core.cover._fetch", return_value=(_png((2, 2, 2)), "ok")):
            embed_cover(target, "https://cdn.example/b.png")

        from mutagen.id3 import ID3

        assert len(ID3(target).getall("APIC")) == 1

    def test_keeps_download_when_image_fails(self, temp_dir: Path) -> None:
        """Una carátula que no se puede bajar nunca debe tumbar la descarga."""
        target = _mp3(temp_dir / "cancion.mp3")
        before = target.read_bytes()

        with patch("media_dl.core.cover._fetch", return_value=(None, "no se pudo descargar")):
            assert embed_cover(target, "https://cdn.example/cae.png") is False

        assert target.read_bytes() == before


class TestEmbedCoverEdgeCases:
    def test_no_url_is_a_noop(self, temp_dir: Path) -> None:
        target = _mp3(temp_dir / "cancion.mp3")
        assert embed_cover(target, None) is False
        assert has_cover(target) is False

    def test_missing_file_is_a_noop(self, temp_dir: Path) -> None:
        with patch("media_dl.core.cover._fetch") as fetch:
            assert embed_cover(temp_dir / "nada.mp3", "https://cdn.example/c.png") is False
        fetch.assert_not_called()

    def test_mp3_import_is_static_so_pyinstaller_bundles_mutagen(self) -> None:
        """El import de mutagen tiene que ser una sentencia, no dinámico.

        PyInstaller solo lee sentencias de import. Con un
        importlib.import_module, mutagen deja de entrar en el binario,
        embed_cover se traga el ImportError y las descargas salen sin
        portada sin decir nada. Pasó de verdad al intentar callar a mypy,
        así que el guard se queda aquí y no en la buena memoria.
        """
        source = Path(cover_module.__file__).read_text()
        assert 'importlib.import_module("mutagen' not in source
        assert "from mutagen.id3 import APIC, ID3" in source

    def test_explain_says_why_it_failed(self, temp_dir: Path) -> None:
        """Un False a secas es lo que escondió el bug de empaquetado.

        embed_cover devolvía False con la boca cerrada y nadie sabía si era
        que no había red, que el contenedor no servía o que mutagen no estaba
        en el binario. explain_embed_cover dice cuál de las tres.
        """
        target = _mp3(temp_dir / "cancion.mp3")

        ok, reason = explain_embed_cover(target, None)
        assert ok is False
        assert "URL" in reason

        ok, reason = explain_embed_cover(temp_dir / "nada.mp3", "https://cdn.example/c.png")
        assert ok is False
        assert "no existe" in reason

        target2 = temp_dir / "cancion.ogg"
        target2.write_bytes(b"OggS" + b"\x00" * 64)
        ok, reason = explain_embed_cover(target2, "data:image/jpeg;base64," + _TINY_B64)
        assert ok is False
        assert "soportado" in reason

    def test_self_test_passes_without_network(self) -> None:
        """El self-test tiene que poder fallar si el binario va mal.

        Es lo que usa doctor, y por tanto lo que decide si la CI acepta el
        binario. Se hace con una imagen en un data: URL para que el resultado
        dependa solo de mutagen y no de si ese día hay red: aquí se comprueba
        Con urlopen revuelto, aun así tiene que pasar.
        """
        with patch("urllib.request.urlopen", side_effect=AssertionError("no debe haber red")):
            ok, reason = self_test()
        assert ok is True, reason
        assert reason == "portada incrustada"

    def test_uses_the_bundled_ca_in_a_frozen_binary(self) -> None:
        """En el bundle hay que darle a urllib la CA que va dentro.

        PyInstaller solo mete certifi como dato y fija SSL_CERT_FILE, pero no
        lo importa al PYZ, así que un urlopen a secas se queda sin emisor y
        falla con CERTIFICATE_VERIFY_FAILED. Pasó en el binario de la CI: el
        audio llegaba (va por requests/httpx, que sí usan certifi) y la
        portada no.
        """
        ca = certifi.where()
        with (
            patch.dict(os.environ, {"SSL_CERT_FILE": ca}),
            patch.object(sys, "_MEIPASS", "", create=True),
            patch("media_dl.core.cover.urllib.request.urlopen") as urlopen,
        ):
            urlopen.return_value.__enter__.return_value.read.return_value = b"imagen"
            _imagen, motivo = cover_module._fetch("https://cdn.example/c.jpg")

        assert motivo == "ok"
        assert urlopen.call_args.kwargs["context"] is not None

    def test_a_broken_ca_path_falls_back_instead_of_failing(self) -> None:
        """Un SSL_CERT_FILE que no vale no puede tumbar la descarga."""
        with (
            patch.dict(os.environ, {"SSL_CERT_FILE": "/no/existe/cacert.pem"}, clear=False),
            patch("media_dl.core.cover.urllib.request.urlopen") as urlopen,
        ):
            urlopen.return_value.__enter__.return_value.read.return_value = b"imagen"
            _imagen, motivo = cover_module._fetch("https://cdn.example/c.jpg")

        assert motivo == "ok"
        assert urlopen.call_args.kwargs["context"] is None

    def test_without_a_bundled_ca_it_uses_the_system_one(self) -> None:
        """Fuera del bundle, urllib se apaña con la CA del sistema."""
        with (
            patch.dict(os.environ, {"SSL_CERT_FILE": "/no/existe/cacert.pem"}, clear=False),
            patch.object(sys, "_MEIPASS", "", create=True),
            patch("media_dl.core.cover.urllib.request.urlopen") as urlopen,
        ):
            urlopen.return_value.__enter__.return_value.read.return_value = b"imagen"
            _imagen, motivo = cover_module._fetch("https://cdn.example/c.jpg")

        assert motivo == "ok"
        assert urlopen.call_args.kwargs["context"] is None

    def test_data_url_images_need_no_network(self, temp_dir: Path) -> None:
        target = _mp3(temp_dir / "cancion.mp3")
        ok, reason = explain_embed_cover(target, "data:image/jpeg;base64," + _TINY_B64)
        assert ok is True, reason
        assert has_cover(target) is True

    def test_data_url_rejects_non_images_and_garbage(self) -> None:
        assert cover_module._decode_data_url("data:text/plain;base64,aGk=") is None
        assert cover_module._decode_data_url("data:image/png,notbase64") is None
        assert cover_module._decode_data_url("https://cdn.example/c.png") is None
        assert cover_module._decode_data_url("data:image/jpeg;base64,!!!") is None

    def test_unsupported_container_is_ignored(self, temp_dir: Path) -> None:
        target = temp_dir / "cancion.ogg"
        target.write_bytes(b"OggS" + b"\x00" * 64)

        with patch("media_dl.core.cover._fetch", return_value=(_png(), "ok")):
            assert embed_cover(target, "https://cdn.example/cover.png") is False
        assert has_cover(target) is False

    def test_download_failure_returns_none(self) -> None:
        from media_dl.core.cover import _fetch

        with patch("urllib.request.urlopen", side_effect=OSError("sin red")):
            assert _fetch("https://cdn.example/cover.png")[0] is None

    def test_fetch_returns_bytes(self) -> None:
        from media_dl.core.cover import _fetch

        png = _png()
        with patch("urllib.request.urlopen", return_value=_FakeResponse(png)):
            assert _fetch("https://cdn.example/cover.png") == (png, "ok")

    def test_ca_status_with_bundled_certifi(self) -> None:
        """Si hay un certifi empaquetado en el bundle, ca_status lo usa."""
        with tempfile.TemporaryDirectory() as tmp:
            ca_dir = Path(tmp) / "certifi"
            ca_dir.mkdir()
            ca_file = ca_dir / "cacert.pem"
            ca_file.write_text("-----BEGIN CERTIFICATE-----\n")
            with patch.object(sys, "_MEIPASS", tmp, create=True):
                ok, reason = cover_module.ca_status()
            assert ok is True
            assert "certifi" in reason

    def test_ca_status_with_ssl_cert_file_env(self) -> None:
        """SSL_CERT_FILE apuntando a un archivo existente es suficiente."""
        with tempfile.TemporaryDirectory() as tmp:
            ca = Path(tmp) / "cacert.pem"
            ca.write_text("-----BEGIN CERTIFICATE-----\n")
            with (
                patch.dict(os.environ, {"SSL_CERT_FILE": str(ca)}),
                patch.object(sys, "_MEIPASS", None, create=True),
            ):
                ok, reason = cover_module.ca_status()
            assert ok is True
            assert "SSL_CERT_FILE" in reason

    def test_ca_status_uses_system_default_when_no_bundle(self) -> None:
        """Sin bundle ni env, usa las rutas por defecto del sistema."""
        with (
            patch.object(sys, "_MEIPASS", None, create=True),
            patch.dict(os.environ, {}, clear=True),
            patch("media_dl.core.cover.ssl.get_default_verify_paths") as vpaths,
        ):
            vpaths.return_value = type(
                "obj", (), {"openssl_cafile": certifi.where(), "openssl_capath": ""}
            )()
            ok, reason = cover_module.ca_status()
            assert ok is True
            assert "CA del sistema" in reason

    def test_ca_status_fails_when_no_source_exists(self) -> None:
        """Si no hay NINGUNA fuente de CA, HTTPS por urllib está roto."""
        with (
            patch.object(sys, "_MEIPASS", None, create=True),
            patch.dict(os.environ, {}, clear=True),
            patch("media_dl.core.cover.ssl.get_default_verify_paths") as vpaths,
        ):
            vpaths.return_value = type(
                "obj", (), {"openssl_cafile": "/no/existe.pem", "openssl_capath": "/no/existe"}
            )()
            ok, reason = cover_module.ca_status()
            assert ok is False
            assert "NINGUNA" in reason
