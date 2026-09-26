"""Tests for the download command helpers and batch flow."""

import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from media_dl.cli.commands.download import (
    BEST_VIDEO,
    _build_batch_request,
    _merge_postprocessors,
    _select_video_quality,
    run_audio,
    run_batch,
    run_video,
)
from media_dl.config import Settings
from media_dl.core.cover import has_cover
from media_dl.core.models import DownloadRequest, Format, MediaInfo


@pytest.fixture
def settings(tmp_path):
    return Settings(
        download_path=tmp_path / "downloads",
        config_dir=tmp_path / "config",
        db_path=tmp_path / "config" / "history.db",
    )


@pytest.fixture
def info():
    return MediaInfo(
        id="abc",
        title="Test",
        url="https://youtube.com/watch?v=abc",
        platform="YouTube",
        formats=[
            Format(format_id=str(h), ext="mp4", height=h, vcodec="v", acodec="a")
            for h in (2160, 1080, 720, 480, 360)
        ],
    )


class TestSelectVideoQuality:
    def test_auto_uses_best(self, info, settings):
        assert _select_video_quality(info, settings, "auto") == BEST_VIDEO
        assert _select_video_quality(info, settings, None) == BEST_VIDEO

    def test_exact_height(self, info, settings):
        assert _select_video_quality(info, settings, "720") == (
            "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        )

    def test_accepts_suffix_p(self, info, settings):
        assert "height<=1080" in _select_video_quality(info, settings, "1080p")

    def test_rounds_down_when_unavailable(self, info, settings):
        """Asking 900 must not silently upgrade to 1080."""
        assert "height<=720" in _select_video_quality(info, settings, "900")

    def test_rounds_up_when_nothing_fits(self, info, settings):
        assert "height<=360" in _select_video_quality(info, settings, "144")

    def test_garbage_falls_back_to_best(self, info, settings):
        assert _select_video_quality(info, settings, "basura") == BEST_VIDEO

    def test_uses_setting_when_no_override(self, info, tmp_path):
        settings = Settings(
            download_path=tmp_path / "d",
            config_dir=tmp_path / "c",
            db_path=tmp_path / "c" / "h.db",
            default_video_quality="480",
        )
        assert "height<=480" in _select_video_quality(info, settings)

    def test_no_formats(self, settings):
        empty = MediaInfo(id="x", title="t", url="u", platform="p")
        assert "height<=720" in _select_video_quality(empty, settings, "720")


class TestMergePostprocessors:
    def test_no_duplicates(self, settings):
        opts = {
            "postprocessors": [
                {"key": "EmbedThumbnail", "already_have_thumbnail": False},
                {"key": "FFmpegMetadata"},
            ]
        }
        _merge_postprocessors(opts, settings)
        keys = [p["key"] for p in opts["postprocessors"]]

        assert keys.count("EmbedThumbnail") == 1
        assert keys.count("FFmpegMetadata") == 1

    def test_adds_missing(self, settings):
        opts: dict = {}
        _merge_postprocessors(opts, settings)

        assert [p["key"] for p in opts["postprocessors"]] == [
            "EmbedThumbnail",
            "FFmpegMetadata",
        ]

    def test_respects_disabled(self, tmp_path):
        settings = Settings(
            download_path=tmp_path / "d",
            config_dir=tmp_path / "c",
            db_path=tmp_path / "c" / "h.db",
            embed_thumbnail=False,
            embed_metadata=False,
        )
        opts: dict = {}
        _merge_postprocessors(opts, settings)

        assert "postprocessors" not in opts


class TestBuildBatchRequest:
    def test_video_uses_quality_selector(self, info, settings):
        request = _build_batch_request("u", info, "video", settings, None, False, "mp3", 192)

        assert request.media_type == "video"
        assert request.strategy == "normal"
        assert request.quality == BEST_VIDEO

    def test_video_respects_configured_quality(self, info, tmp_path):
        settings = Settings(
            download_path=tmp_path / "d",
            config_dir=tmp_path / "c",
            db_path=tmp_path / "c" / "h.db",
            default_video_quality="720",
        )
        request = _build_batch_request("u", info, "video", settings, None, False, "mp3", 192)

        assert "height<=720" in (request.quality or "")

    def test_audio_uses_format(self, info, settings):
        request = _build_batch_request("u", info, "audio", settings, None, True, "original", 192)

        assert request.media_type == "audio"
        assert request.format == "original"
        assert request.strategy == "ultra"


class TestRunBatch:
    def test_rejects_bad_type(self, settings):
        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            pytest.raises(typer.Exit),
        ):
            run_batch(urls=["https://x.com/a"], media_type="pelicula")

    def test_rejects_bad_bitrate(self, settings):
        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            pytest.raises(typer.Exit),
        ):
            run_batch(urls=["https://x.com/a"], media_type="audio", bitrate=999)

    def test_rejects_missing_file(self, settings, tmp_path):
        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            pytest.raises(typer.Exit),
        ):
            run_batch(file=tmp_path / "no-existe.txt")

    def test_no_valid_urls(self, settings):
        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            pytest.raises(typer.Exit),
        ):
            run_batch(urls=["no-es-url", ""])

    def test_records_history_for_each_success(self, settings, info, tmp_path):
        target = tmp_path / "salida"
        target.mkdir()

        repo = MagicMock()
        repo.is_duplicate.return_value = None

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get") as factory,
            patch("media_dl.cli.commands.download._run_async", return_value=info),
            patch("media_dl.cli.commands.download._download_batch_item") as download,
        ):
            strategy = MagicMock()
            strategy.is_available.return_value = True
            strategy.build_args.return_value = {}
            factory.return_value = strategy

            first = target / "uno.mp4"
            first.write_bytes(b"x" * 128)
            second = target / "dos.mp4"
            second.write_bytes(b"y" * 256)
            download.side_effect = [str(first), str(second)]

            run_batch(urls=["https://a.com/1", "https://a.com/2"], output=str(target), concurrent=2)

        assert repo.add.call_count == 2

    def test_isolates_failures(self, settings, info, tmp_path):
        repo = MagicMock()
        repo.is_duplicate.return_value = None

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get") as factory,
            patch("media_dl.cli.commands.download._run_async", return_value=info),
            patch("media_dl.cli.commands.download._download_batch_item") as download,
        ):
            strategy = MagicMock()
            strategy.is_available.return_value = True
            strategy.build_args.return_value = {}
            factory.return_value = strategy

            good = tmp_path / "ok.mp4"
            good.write_bytes(b"y" * 64)
            download.side_effect = [RuntimeError("boom"), str(good)]

            run_batch(urls=["https://a.com/1", "https://a.com/2"], concurrent=2)

        # El que falla no llega al historial, el que funciona sí.
        assert repo.add.call_count == 1

    def test_skips_duplicates(self, settings, info):
        repo = MagicMock()
        repo.is_duplicate.return_value = MagicMock(title="Ya estaba")

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get"),
            patch("media_dl.cli.commands.download._run_async", return_value=info),
            patch("media_dl.cli.commands.download._download_batch_item") as download,
        ):
            run_batch(urls=["https://a.com/1"])

        download.assert_not_called()
        repo.add.assert_not_called()

    def test_extraction_failure_is_counted(self, settings):
        repo = MagicMock()

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get"),
            patch("media_dl.cli.commands.download._run_async", side_effect=RuntimeError("sin red")),
        ):
            run_batch(urls=["https://a.com/1", "https://a.com/2"])

        repo.add.assert_not_called()


class TestQualityPrompting:
    """El programa debe preguntar la calidad/formato, salvo que se le indique."""

    @pytest.fixture
    def info(self):
        return MediaInfo(
            id="abc",
            title="Test",
            url="https://youtube.com/watch?v=abc",
            platform="YouTube",
            duration=300,
            formats=[
                Format(format_id="1", ext="mp4", height=h, vcodec="v", acodec="a")
                for h in (2160, 1080, 720)
            ],
        )

    def _run(
        self,
        info,
        settings,
        fn,
        *,
        interactive=True,
        quality_answer="1080",
        format_answer="mp3",
        bitrate_answer=192,
        tmp_path=None,
        **kwargs,
    ):
        """Ejecuta fn con todo parcheado; devuelve los mocks de las preguntas."""
        # La descarga "mockeada" tiene que dejar un archivo real, porque el
        # código comprueba que existe antes de dizer que ha ido bien.
        destino = (tmp_path or Path(tempfile.mkdtemp())) / "descarga.mp4"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"x" * 64)

        repo = MagicMock()
        repo.is_duplicate.return_value = None
        strategy = MagicMock()
        strategy.is_available.return_value = True
        strategy.build_args.return_value = {}

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get", return_value=strategy),
            patch("media_dl.cli.commands.download._run_async", return_value=info),
            patch(
                "media_dl.cli.commands.download._download_with_retry",
                return_value=str(destino),
            ),
            patch("media_dl.cli.commands.download._can_ask", return_value=interactive),
            patch("media_dl.cli.commands.download.prompt_quality") as p_quality,
            patch("media_dl.cli.commands.download.prompt_audio_format") as p_format,
            patch("media_dl.cli.commands.download.prompt_audio_bitrate") as p_bitrate,
        ):
            p_quality.return_value = quality_answer
            p_format.return_value = format_answer
            p_bitrate.return_value = bitrate_answer
            fn(**kwargs)

        return {
            "quality": p_quality,
            "format": p_format,
            "bitrate": p_bitrate,
            "repo": repo,
        }

    # ---------- vídeo ----------

    def test_video_asks_when_interactive(self, info, settings):
        mocks = self._run(info, settings, run_video, url="https://youtube.com/watch?v=abc")
        mocks["quality"].assert_called_once()
        # las alturas se pasan sin la 'p': ['2160', '1080', '720']
        assert mocks["quality"].call_args.args[0] == ["2160", "1080", "720"]

    def test_video_does_not_ask_when_quality_given(self, info, settings):
        mocks = self._run(
            info, settings, run_video, url="https://youtube.com/watch?v=abc", quality="480"
        )
        mocks["quality"].assert_not_called()

    def test_video_does_not_ask_without_terminal(self, info, settings):
        mocks = self._run(
            info, settings, run_video, url="https://youtube.com/watch?v=abc", interactive=False
        )
        mocks["quality"].assert_not_called()

    def test_video_uses_configured_default_as_marker(self, info, tmp_path):
        settings = Settings(
            download_path=tmp_path / "d",
            config_dir=tmp_path / "c",
            db_path=tmp_path / "c" / "h.db",
            default_video_quality="720",
        )
        mocks = self._run(info, settings, run_video, url="https://youtube.com/watch?v=abc")
        assert mocks["quality"].call_args.kwargs["default"] == "720"

    def test_video_skips_prompt_without_video_formats(self, settings):
        solo_audio = MediaInfo(
            id="a", title="a", url="https://soundcloud.com/x/y", platform="SoundCloud"
        )
        mocks = self._run(solo_audio, settings, run_video, url="https://soundcloud.com/x/y")
        mocks["quality"].assert_not_called()

    # ---------- audio ----------

    def test_audio_asks_format(self, info, settings):
        mocks = self._run(info, settings, run_audio, url="https://youtube.com/watch?v=abc")
        mocks["format"].assert_called_once()

    def test_audio_asks_bitrate_only_for_mp3(self, info, settings):
        mocks = self._run(info, settings, run_audio, url="https://youtube.com/watch?v=abc")
        mocks["bitrate"].assert_called_once()

    def test_audio_original_skips_bitrate_question(self, info, settings, tmp_path):
        """Si eliges 'original', el bitrate de MP3 no tiene sentido: no se pregunta."""
        mocks = self._run(
            info,
            settings,
            run_audio,
            url="https://youtube.com/watch?v=abc",
            format_answer="original",
            tmp_path=tmp_path,
        )
        mocks["bitrate"].assert_not_called()
        assert mocks["repo"].add.call_args.kwargs["quality"] == "original"

    def test_audio_does_not_ask_when_flags_given(self, info, settings):
        mocks = self._run(
            info,
            settings,
            run_audio,
            url="https://youtube.com/watch?v=abc",
            audio_format="mp3",
            bitrate=320,
        )
        mocks["format"].assert_not_called()
        mocks["bitrate"].assert_not_called()

    def test_audio_without_terminal_uses_config(self, info, settings, tmp_path):
        """Sin terminal se aplica la configuración, sin preguntar."""
        config = Settings(
            download_path=tmp_path / "d",
            config_dir=tmp_path / "c",
            db_path=tmp_path / "c" / "h.db",
            default_audio_format="original",
            default_audio_bitrate=320,
        )
        mocks = self._run(
            info, config, run_audio, url="https://youtube.com/watch?v=abc", interactive=False
        )
        mocks["format"].assert_not_called()
        assert mocks["repo"].add.call_args.kwargs["quality"] == "original"

    def test_audio_uses_config_defaults_as_markers(self, info, tmp_path):
        config = Settings(
            download_path=tmp_path / "d",
            config_dir=tmp_path / "c",
            db_path=tmp_path / "c" / "h.db",
            default_audio_format="mp3",
            default_audio_bitrate=320,
        )
        mocks = self._run(info, config, run_audio, url="https://youtube.com/watch?v=abc")
        assert mocks["format"].call_args.kwargs["default"] == "mp3"
        assert mocks["bitrate"].call_args.kwargs["default"] == 320


class TestNoOverwrite:
    """Al volver a descargar lo mismo nunca se pisa el archivo anterior."""

    @pytest.fixture
    def settings(self, tmp_path):
        return Settings(
            download_path=tmp_path / "descargas",
            config_dir=tmp_path / "config",
            db_path=tmp_path / "config" / "history.db",
        )

    @pytest.fixture
    def info(self):
        return MediaInfo(
            id="abc123",
            title="Mi vídeo",
            url="https://youtube.com/watch?v=abc123",
            platform="YouTube",
            duration=100,
            formats=[Format(format_id="1", ext="mp4", height=720, vcodec="v", acodec="a")],
        )

    # ---------- el cálculo del nombre ----------

    def test_free_stem_when_nothing_exists(self, tmp_path):
        from media_dl.cli.commands.download import _free_output_stem

        assert _free_output_stem(tmp_path, "cancion [abc]") == "cancion [abc]"

    def test_free_stem_avoids_existing(self, tmp_path):
        from media_dl.cli.commands.download import _free_output_stem

        (tmp_path / "cancion [abc].mp4").write_bytes(b"x")
        assert _free_output_stem(tmp_path, "cancion [abc]") == "cancion [abc] (1)"

    def test_free_stem_ignores_extension(self, tmp_path):
        """Un .m4a previo también cuenta como ocupado."""
        from media_dl.cli.commands.download import _free_output_stem

        (tmp_path / "cancion [abc].m4a").write_bytes(b"x")
        assert _free_output_stem(tmp_path, "cancion [abc]") == "cancion [abc] (1)"

    def test_free_stem_increments(self, tmp_path):
        from media_dl.cli.commands.download import _free_output_stem

        (tmp_path / "cancion [abc].mp4").write_bytes(b"x")
        (tmp_path / "cancion [abc] (1).mp4").write_bytes(b"x")
        assert _free_output_stem(tmp_path, "cancion [abc]") == "cancion [abc] (2)"

    def test_stem_with_brackets_is_escaped(self, tmp_path):
        """Los corchetes del nombre son comodines de glob: hay que escaparlos."""
        from media_dl.cli.commands.download import _free_output_stem

        (tmp_path / "song [live].mp4").write_bytes(b"x")
        assert _free_output_stem(tmp_path, "song [live]") == "song [live] (1)"

    def test_outtmpl_uses_stem(self, settings, info):
        from media_dl.cli.commands.download import _build_ydl_opts

        request = DownloadRequest(url="u", media_type="video", quality=BEST_VIDEO)
        opts = _build_ydl_opts(request, {}, settings, stem="nombre (1)")
        assert opts["outtmpl"].endswith("nombre (1).%(ext)s")

    def test_outtmpl_default_unchanged(self, settings, info):
        from media_dl.cli.commands.download import _build_ydl_opts

        request = DownloadRequest(url="u", media_type="video", quality=BEST_VIDEO)
        opts = _build_ydl_opts(request, {}, settings)
        assert opts["outtmpl"].endswith("%(title).100s [%(id)s].%(ext)s")

    # ---------- el flujo completo ----------

    def _run_video(self, info, settings, *, answer_yes, force=False, tmp_path=None):
        repo = MagicMock()
        repo.is_duplicate.return_value = MagicMock(title="Mi vídeo")
        strategy = MagicMock()
        strategy.is_available.return_value = True
        strategy.build_args.return_value = {}

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get", return_value=strategy),
            patch("media_dl.cli.commands.download._run_async", return_value=info),
            patch("media_dl.cli.commands.download._download_with_retry") as download,
            patch("media_dl.cli.commands.download.prompt_yes_no", return_value=answer_yes),
            patch("media_dl.cli.commands.download._can_ask", return_value=False),
        ):
            if answer_yes:
                run_video(url=info.url, force=force)
            else:
                run_video(url=info.url, force=force)
            return repo, download

    def test_answering_no_cancels(self, info, settings):
        _repo, download = self._run_video(info, settings, answer_yes=False)
        download.assert_not_called()

    def test_answering_yes_picks_a_free_name(self, info, settings, tmp_path):
        """Respondiendo 'y' se descarga, pero con otro nombre."""
        salida = settings.download_path
        salida.mkdir(parents=True, exist_ok=True)
        (salida / "Mi vídeo [abc123].mp4").write_bytes(b"viejo")

        _repo, download = self._run_video(info, settings, answer_yes=True)

        opts = download.call_args.args[1]
        assert opts["outtmpl"].endswith("Mi vídeo [abc123] (1).%(ext)s")

    def test_answering_yes_keeps_the_original(self, info, settings):
        salida = settings.download_path
        salida.mkdir(parents=True, exist_ok=True)
        original = salida / "Mi vídeo [abc123].mp4"
        original.write_bytes(b"contenido original")

        self._run_video(info, settings, answer_yes=True)

        # el archivo previo sigue intacto
        assert original.read_bytes() == b"contenido original"

    def test_no_duplicate_uses_normal_template(self, info, settings):
        repo = MagicMock()
        repo.is_duplicate.return_value = None
        strategy = MagicMock()
        strategy.is_available.return_value = True
        strategy.build_args.return_value = {}

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get", return_value=strategy),
            patch("media_dl.cli.commands.download._run_async", return_value=info),
            patch("media_dl.cli.commands.download._download_with_retry") as download,
            patch("media_dl.cli.commands.download._can_ask", return_value=False),
        ):
            run_video(url=info.url)

        opts = download.call_args.args[1]
        assert opts["outtmpl"].endswith("%(title).100s [%(id)s].%(ext)s")

    def test_missing_file_is_not_reported_as_success(self, info, settings, capsys):
        """Si yt-dlp no crea el archivo, no decimos '✅ Completada'."""
        repo = MagicMock()
        repo.is_duplicate.return_value = None
        strategy = MagicMock()
        strategy.is_available.return_value = True
        strategy.build_args.return_value = {}

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get", return_value=strategy),
            patch("media_dl.cli.commands.download._run_async", return_value=info),
            patch(
                "media_dl.cli.commands.download._download_with_retry",
                return_value="/no/existe/nada.mp4",
            ),
            patch("media_dl.cli.commands.download._can_ask", return_value=False),
        ):
            run_video(url=info.url)

        salida = capsys.readouterr().out
        assert "No se creó el archivo" in salida
        assert "Descarga Completada" not in salida
        repo.add.assert_not_called()


class TestMediaUrl:
    """Un extractor puede entregar una URL directa de medios (Spotify)."""

    def test_uses_media_url_when_present(self, settings):
        info = MediaInfo(
            id="spot",
            title="Canción",
            url="https://open.spotify.com/track/spot",
            platform="Spotify",
            media_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        repo = MagicMock()
        repo.is_duplicate.return_value = None
        strategy = MagicMock()
        strategy.is_available.return_value = True
        strategy.build_args.return_value = {}
        destino = settings.download_path / "cancion.mp3"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"x" * 32)

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get", return_value=strategy),
            patch("media_dl.cli.commands.download._run_async", return_value=info),
            patch(
                "media_dl.cli.commands.download._download_with_retry", return_value=str(destino)
            ) as download,
            patch("media_dl.cli.commands.download._can_ask", return_value=False),
        ):
            run_audio(url=info.url, audio_format="mp3", bitrate=192)

        # se descarga la URL resuelta, no la de Spotify
        assert download.call_args.args[0] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # pero el historial guarda la de Spotify
        assert repo.add.call_args.kwargs["url"] == "https://open.spotify.com/track/spot"

    def test_falls_back_to_page_url(self, settings):
        info = MediaInfo(
            id="abc",
            title="Vídeo",
            url="https://youtube.com/watch?v=abc",
            platform="YouTube",
        )
        repo = MagicMock()
        repo.is_duplicate.return_value = None
        strategy = MagicMock()
        strategy.is_available.return_value = True
        strategy.build_args.return_value = {}
        destino = settings.download_path / "v.mp4"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"x" * 32)

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get", return_value=strategy),
            patch("media_dl.cli.commands.download._run_async", return_value=info),
            patch(
                "media_dl.cli.commands.download._download_with_retry", return_value=str(destino)
            ) as download,
            patch("media_dl.cli.commands.download._can_ask", return_value=False),
        ):
            run_video(url=info.url)

        assert download.call_args.args[0] == "https://youtube.com/watch?v=abc"


class TestCoverEmbedding:
    """La carátula que da el extractor debe acabar dentro del archivo.

    Spotify sí entrega la URL de la portada, pero el audio viene de YouTube
    Music sin imagen adjunta, así que el postprocesador de yt-dlp no tiene
    nada que incrustar. Sin este paso el archivo salía sin carátula.
    """

    @pytest.fixture
    def info(self):
        return MediaInfo(
            id="abc",
            title="Creep",
            url="https://open.spotify.com/track/abc",
            platform="Spotify",
            duration=237,
            thumbnail="https://i.scdn.co/image/ab67616d0000b273",
            media_url="https://music.youtube.com/watch?v=xyz",
        )

    def _run(self, info, settings, fn, cover_result=(True, "portada incrustada")):
        repo = MagicMock()
        repo.is_duplicate.return_value = None
        strategy = MagicMock()
        strategy.is_available.return_value = True
        strategy.build_args.return_value = {}
        destino = settings.download_path / "Creep.mp3"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"\xff\xfb\x90\x64" + b"\x00" * 64)

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get", return_value=strategy),
            patch("media_dl.cli.commands.download._run_async", return_value=info),
            patch("media_dl.cli.commands.download._download_with_retry", return_value=str(destino)),
            patch("media_dl.cli.commands.download._can_ask", return_value=False),
            patch("media_dl.cli.commands.download.explain_embed_cover") as embed,
        ):
            embed.return_value = cover_result
            fn(url=info.url)
        return embed, destino

    def test_audio_embeds_the_thumbnail(self, info, settings):
        embed, destino = self._run(info, settings, run_audio)
        embed.assert_called_once()
        assert embed.call_args.args[0] == destino
        assert embed.call_args.args[1] == "https://i.scdn.co/image/ab67616d0000b273"

    def test_respects_the_embed_thumbnail_setting(self, info, settings):
        settings.embed_thumbnail = False
        embed, _destino = self._run(info, settings, run_audio)
        embed.assert_not_called()

    def test_avisa_si_la_portada_no_se_incrusta(self, info, settings, capsys):
        """Sin este aviso, una descarga sin portada no se distingue de un fallo.

        Una vez perdido mutagen del binario, todo funcionaba y las descargas
        salían sin portada con total silencio. Ahora el motivo sale en el
        panel de éxito, que es donde el usuario va a mirar.
        """
        self._run(info, settings, run_audio, cover_result=(False, "no se pudo descargar la imagen"))
        salida = re.sub(r"[│┃|]", " ", capsys.readouterr().out)
        assert "Portada no incrustada" in salida
        assert "no se pudo descargar la imagen" in salida

    def test_really_writes_the_cover(self, info, settings):
        """Sin parches: el archivo descargado acaba con la imagen dentro."""
        repo = MagicMock()
        repo.is_duplicate.return_value = None
        strategy = MagicMock()
        strategy.is_available.return_value = True
        strategy.build_args.return_value = {}
        destino = settings.download_path / "Creep.mp3"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"\xff\xfb\x90\x64" + b"\x00" * 64)

        with (
            patch("media_dl.cli.commands.download.get_settings", return_value=settings),
            patch("media_dl.cli.commands.download.get_extractor"),
            patch("media_dl.cli.commands.download.HistoryRepository", return_value=repo),
            patch("media_dl.cli.commands.download.StrategyFactory.get", return_value=strategy),
            patch("media_dl.cli.commands.download._run_async", return_value=info),
            patch("media_dl.cli.commands.download._download_with_retry", return_value=str(destino)),
            patch("media_dl.cli.commands.download._can_ask", return_value=False),
            patch("media_dl.core.cover._fetch", return_value=(b"\x89PNG-falso", "ok")),
        ):
            run_audio(url=info.url)

        assert has_cover(destino) is True
