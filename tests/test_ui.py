"""Tests for the UI layer: menus, prompts and non-interactive behaviour."""

from unittest.mock import patch

import pytest

from media_dl.core.exceptions import ValidationError
from media_dl.ui import menus, prompts
from media_dl.ui import tables as tables_module


class TestNonInteractive:
    """Regresión: sin terminal, nada puede pedir input ni reventar con EOFError."""

    def test_pause_is_a_noop(self):
        with (
            patch.object(menus, "is_interactive", return_value=False),
            patch.object(menus, "Prompt") as mock_prompt,
        ):
            menus.pause()

        mock_prompt.ask.assert_not_called()

    def test_prompt_yes_no_returns_default(self):
        with patch.object(prompts, "is_interactive", return_value=False):
            assert prompts.prompt_yes_no("¿Seguro?", default=True) is True
            assert prompts.prompt_yes_no("¿Seguro?", default=False) is False

    def test_show_menu_returns_exit(self):
        with patch.object(menus, "is_interactive", return_value=False):
            assert menus.show_menu("TITULO", [("1", "Uno", "")]) == "0"

    def test_prompt_quality_defaults_to_best(self):
        with patch.object(prompts, "is_interactive", return_value=False):
            assert prompts.prompt_quality(["720", "1080"]) == "auto"

    def test_prompt_audio_format_defaults_to_mp3(self):
        with patch.object(prompts, "is_interactive", return_value=False):
            assert prompts.prompt_audio_format() == "mp3"

    def test_prompt_audio_format_honours_configured_default(self):
        with patch.object(prompts, "is_interactive", return_value=False):
            assert prompts.prompt_audio_format(default="original") == "original"

    def test_prompt_audio_bitrate_defaults_to_192(self):
        with patch.object(prompts, "is_interactive", return_value=False):
            assert prompts.prompt_audio_bitrate() == 192

    def test_prompt_audio_bitrate_honours_configured_default(self):
        with patch.object(prompts, "is_interactive", return_value=False):
            assert prompts.prompt_audio_bitrate(default=320) == 320

    def test_prompt_url_fails_fast(self):
        with (
            patch.object(prompts, "is_interactive", return_value=False),
            pytest.raises(ValidationError),
        ):
            prompts.prompt_url()

    def test_prompt_playlist_range_defaults_to_all(self):
        with patch.object(prompts, "is_interactive", return_value=False):
            assert prompts.prompt_playlist_range(10) is None


class TestInteractivePaths:
    def test_show_menu_returns_choice(self):
        with (
            patch.object(menus, "is_interactive", return_value=True),
            patch.object(menus, "Prompt") as mock_prompt,
        ):
            mock_prompt.ask.return_value = "2"
            assert menus.show_menu("T", [("1", "Uno", ""), ("2", "Dos", "")]) == "2"

    def test_prompt_quality_picks_by_index(self):
        with (
            patch.object(prompts, "is_interactive", return_value=True),
            patch.object(prompts, "Prompt") as mock_prompt,
        ):
            mock_prompt.ask.return_value = "1"
            assert prompts.prompt_quality(["720", "1080"]) == "720"

    def test_prompt_quality_last_option_is_auto(self):
        with (
            patch.object(prompts, "is_interactive", return_value=True),
            patch.object(prompts, "Prompt") as mock_prompt,
        ):
            mock_prompt.ask.return_value = "3"
            assert prompts.prompt_quality(["720", "1080"]) == "auto"

    def test_prompt_quality_accepts_heights_with_suffix(self):
        """MediaInfo.available_qualities ya trae la 'p'; no debe salir '720pp'."""
        with (
            patch.object(prompts, "is_interactive", return_value=True),
            patch.object(prompts, "Prompt") as mock_prompt,
        ):
            mock_prompt.ask.return_value = "1"
            assert prompts.prompt_quality(["1080p", "720p"]) == "1080"

    def test_prompt_quality_marks_configured_default(self):
        with (
            patch.object(prompts, "is_interactive", return_value=True),
            patch.object(prompts, "Prompt") as mock_prompt,
        ):
            mock_prompt.ask.return_value = "1"
            prompts.prompt_quality(["1080p", "720p"], default="720p")
            shown = "\n".join(str(c) for c in mock_prompt.method_calls)
            assert shown  # el prompt se emitió

    def test_prompt_quality_default_marker_rendered(self):
        import io

        from rich.console import Console

        buffer = io.StringIO()
        fake = Console(file=buffer, width=100, force_terminal=False, markup=True)
        with (
            patch.object(prompts, "console", fake),
            patch.object(prompts, "is_interactive", return_value=True),
            patch.object(prompts, "Prompt") as mock_prompt,
        ):
            mock_prompt.ask.return_value = "1"
            prompts.prompt_quality(["1080p", "720p"], default="720p")
        salida = buffer.getvalue()

        assert "1080p" in salida
        assert "720p" in salida
        assert "1080pp" not in salida
        assert "actual" in salida

    def test_prompt_audio_bitrate_picks_320(self):
        with (
            patch.object(prompts, "is_interactive", return_value=True),
            patch.object(prompts, "Prompt") as mock_prompt,
        ):
            mock_prompt.ask.return_value = "1"
            assert prompts.prompt_audio_bitrate() == 320

    def test_prompt_playlist_range_all(self):
        with (
            patch.object(prompts, "is_interactive", return_value=True),
            patch.object(prompts, "Prompt") as mock_prompt,
        ):
            mock_prompt.ask.return_value = "all"
            assert prompts.prompt_playlist_range(10) is None

    def test_prompt_playlist_range_specific(self):
        with (
            patch.object(prompts, "is_interactive", return_value=True),
            patch.object(prompts, "Prompt") as mock_prompt,
        ):
            mock_prompt.ask.return_value = "1-3"
            assert prompts.prompt_playlist_range(10) == "1-3"

    def test_prompt_subtitle_languages(self):
        with (
            patch.object(prompts, "is_interactive", return_value=True),
            patch.object(prompts, "Prompt") as mock_prompt,
        ):
            mock_prompt.ask.return_value = "es, EN ,fr"
            assert prompts.prompt_subtitle_languages() == ["es", "en", "fr"]


class TestParseRange:
    def test_simple(self):
        assert prompts.parse_range("1-5", 10) == [0, 1, 2, 3, 4]

    def test_mixed(self):
        assert prompts.parse_range("1-2,5", 10) == [0, 1, 4]

    def test_single_items(self):
        assert prompts.parse_range("1,3,5", 10) == [0, 2, 4]

    def test_deduplicates_and_sorts(self):
        assert prompts.parse_range("3,1,3", 10) == [0, 2]

    def test_ignores_blank_parts(self):
        assert prompts.parse_range("1,,2,", 10) == [0, 1]

    @pytest.mark.parametrize("value", ["all", "TODO", "*", "  All "])
    def test_all_returns_none(self, value):
        assert prompts.parse_range(value, 10) is None

    def test_reversed_range(self):
        with pytest.raises(ValueError, match="Formato de rango inválido"):
            prompts.parse_range("5-3", 10)

    def test_out_of_bounds(self):
        with pytest.raises(ValueError, match="Índice inválido"):
            prompts.parse_range("11", 10)

    def test_zero_index(self):
        with pytest.raises(ValueError, match="Índice inválido"):
            prompts.parse_range("0", 10)

    def test_non_numeric(self):
        with pytest.raises(ValueError, match="Índice inválido"):
            prompts.parse_range("abc", 10)

    def test_non_numeric_range(self):
        with pytest.raises(ValueError, match="Formato de rango inválido"):
            prompts.parse_range("1-x", 10)


class TestMarkupInjection:
    """Regresión: Rich se come los corchetes como si fueran etiquetas de estilo.

    Nuestro template de nombre es '%(title).100s [%(id)s].%(ext)s', así que
    cualquier descarga mostraba un nombre que no existía en disco.
    """

    def _render(self, fn, *args, **kwargs) -> str:
        """Render through a throwaway Console and return what the user sees."""
        from rich.console import Console

        fake = Console(width=200, force_terminal=False, markup=True, emoji=False)
        with (
            patch.object(menus, "console", fake),
            patch.object(tables_module, "console", fake),
            fake.capture() as capture,
        ):
            fn(*args, **kwargs)
        return capture.get()

    def test_panels_keep_brackets(self):
        from media_dl.ui import (
            show_error_panel,
            show_info_panel,
            show_success_panel,
            show_warning_panel,
        )

        for panel in (
            show_info_panel,
            show_success_panel,
            show_error_panel,
            show_warning_panel,
        ):
            salida = self._render(panel, "T", "Archivo: mi video [id123].mp4")
            assert "[id123].mp4" in salida, panel.__name__

    def test_panel_title_with_brackets(self):
        from media_dl.ui import show_success_panel

        salida = self._render(show_success_panel, "✅ OK [2]", "contenido")
        assert "OK [2]" in salida

    def test_history_table_keeps_brackets(self):
        from datetime import datetime

        from media_dl.core.history.models import DownloadHistory
        from media_dl.ui.tables import create_history_table

        record = DownloadHistory(
            title="Cancion [live] (2024)",
            platform="YouTube",
            media_type="video",
            file_size=1024,
            download_date=datetime(2026, 1, 2, 3, 4),
        )
        table = create_history_table([record])
        salida = self._render(lambda: tables_module.console.print(table))

        assert "[live]" in salida

    def test_media_info_table_keeps_brackets(self):
        from media_dl.core.models import MediaInfo
        from media_dl.ui.tables import create_media_info_table

        info = MediaInfo(
            id="x",
            title="Tema [remaster] 2024",
            url="https://x.com/a?b=1",
            platform="YouTube",
        )
        table = create_media_info_table(info)
        salida = self._render(lambda: tables_module.console.print(table))

        assert "[remaster]" in salida

    def test_playlist_table_keeps_brackets(self):
        from media_dl.core.models import PlaylistEntry
        from media_dl.ui.tables import create_playlist_table

        entries = [PlaylistEntry(id="1", title="Video [HD]", url="u")]
        table = create_playlist_table(entries)
        salida = self._render(lambda: tables_module.console.print(table))

        assert "[HD]" in salida


class TestTables:
    def test_format_size(self):
        from media_dl.ui.tables import format_size

        assert format_size(0) == "Desconocido"
        assert format_size(None) == "Desconocido"
        assert format_size(500) == "500.00 B"
        assert format_size(1024) == "1.00 KB"
        assert format_size(1024**2) == "1.00 MB"
        assert format_size(1024**3) == "1.00 GB"

    def test_format_size_keeps_precision(self):
        """Regresión: reutilizar la variable int como float perdía decimales."""
        from media_dl.ui.tables import format_size

        assert format_size(1536) == "1.50 KB"
        assert format_size(1610612736) == "1.50 GB"

    def test_format_duration(self):
        from media_dl.ui.tables import format_duration

        assert format_duration(None) == "N/A"
        assert format_duration(0) == "N/A"
        assert format_duration(30) == "0m 30s"
        assert format_duration(90) == "1m 30s"
        assert format_duration(3661) == "1h 1m 1s"

    def test_history_table_without_date(self):
        """Regresión: download_date None reventaba en strftime."""
        from media_dl.core.history.models import DownloadHistory
        from media_dl.ui.tables import create_history_table

        record = DownloadHistory(title="x", download_date=None)
        table = create_history_table([record])

        assert table.row_count == 1
