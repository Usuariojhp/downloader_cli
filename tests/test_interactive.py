"""Tests for the interactive menu mode."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from media_dl.config import Settings
from media_dl.main import app, interactive


@pytest.fixture
def settings(tmp_path):
    return Settings(
        download_path=tmp_path / "downloads",
        config_dir=tmp_path / "config",
        db_path=tmp_path / "config" / "history.db",
        download_mode="normal",
    )


def _menu(*choices):
    """Patch show_main_menu so each loop iteration returns the next choice."""
    iterator = iter(choices)
    return patch("media_dl.ui.show_main_menu", side_effect=lambda: next(iterator))


class TestMenuRouting:
    def test_option_0_exits(self, settings):
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("0"),
        ):
            result = CliRunner().invoke(app, ["interactive"])

        assert result.exit_code == 0

    def test_option_1_downloads_video(self, settings):
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("1", "0"),
            patch("typer.prompt", return_value="https://youtube.com/watch?v=abc"),
            patch("media_dl.cli.commands.download.run_video") as run_video,
            patch("media_dl.ui.pause"),
        ):
            result = CliRunner().invoke(app, ["interactive"])

        assert result.exit_code == 0
        run_video.assert_called_once()
        assert run_video.call_args.kwargs["url"] == "https://youtube.com/watch?v=abc"
        # el modo de descarga sale de la configuración, no de un default sucio
        assert run_video.call_args.kwargs["ultra"] is False

    def test_option_2_asks_audio_settings(self, settings):
        """Sin audio_format/bitrate explícitos, run_audio debe preguntar."""
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("2", "0"),
            patch("typer.prompt", return_value="https://youtube.com/watch?v=abc"),
            patch("media_dl.cli.commands.download.run_audio") as run_audio,
            patch("media_dl.ui.pause"),
        ):
            CliRunner().invoke(app, ["interactive"])

        kwargs = run_audio.call_args.kwargs
        assert kwargs["audio_format"] is None
        assert kwargs["bitrate"] is None
        # antes pasaba format=... y era el builtin; ahora el nombre es explícito
        assert "format" not in kwargs

    def test_option_1_asks_quality(self, settings):
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("1", "0"),
            patch("typer.prompt", return_value="https://youtube.com/watch?v=abc"),
            patch("media_dl.cli.commands.download.run_video") as run_video,
            patch("media_dl.ui.pause"),
        ):
            CliRunner().invoke(app, ["interactive"])

        assert run_video.call_args.kwargs["quality"] is None

    def test_option_3_runs_batch(self, settings):
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("3", "0"),
            patch("media_dl.cli.commands.download.run_batch") as run_batch,
            patch("media_dl.ui.pause"),
        ):
            CliRunner().invoke(app, ["interactive"])

        assert run_batch.call_args.kwargs["media_type"] == "video"

    def test_option_4_shows_history(self, settings):
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("4", "0"),
            patch("media_dl.cli.commands.history.show_history") as show_history,
            patch("media_dl.ui.pause"),
        ):
            CliRunner().invoke(app, ["interactive"])

        show_history.assert_called_once()

    def test_option_6_runs_doctor(self, settings):
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("6", "0"),
            patch("media_dl.cli.commands.doctor.run_doctor") as run_doctor,
        ):
            CliRunner().invoke(app, ["interactive"])

        run_doctor.assert_called_once()

    def test_empty_url_does_nothing(self, settings):
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("1", "0"),
            patch("typer.prompt", return_value="   "),
            patch("media_dl.cli.commands.download.run_video") as run_video,
            patch("media_dl.ui.pause"),
        ):
            CliRunner().invoke(app, ["interactive"])

        run_video.assert_not_called()


class TestConfigSubmenu:
    def _run_config(self, settings, *opts):
        """Enter the config submenu, pick ``opts`` and return the patched mocks."""
        mocks = {}
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("5", "0"),
            patch("typer.prompt", side_effect=list(opts)),
            patch("media_dl.cli.commands.config.show_config") as show_config,
            patch("media_dl.cli.commands.config.set_config") as set_config,
            patch("media_dl.cli.commands.config.reset_config") as reset_config,
            patch("media_dl.cli.commands.config.show_paths") as show_paths,
        ):
            mocks = {
                "show": show_config,
                "set": set_config,
                "reset": reset_config,
                "paths": show_paths,
            }
            CliRunner().invoke(app, ["interactive"])
        return mocks

    def test_show(self, settings):
        self._run_config(settings, 1, 0)["show"].assert_called_once()

    def test_set(self, settings):
        self._run_config(settings, 2, "retry_attempts", 0)["set"].assert_called_once_with(
            "retry_attempts"
        )

    def test_reset(self, settings):
        self._run_config(settings, 3, 0)["reset"].assert_called_once()

    def test_paths(self, settings):
        self._run_config(settings, 4, 0)["paths"].assert_called_once()


class TestResilience:
    def test_error_does_not_kill_the_loop(self, settings):
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("4", "0"),
            patch("media_dl.cli.commands.history.show_history", side_effect=RuntimeError("boom")),
            patch("media_dl.ui.pause"),
        ):
            result = CliRunner().invoke(app, ["interactive"])

        assert result.exit_code == 0
        assert "boom" in result.output

    def test_typer_exit_does_not_kill_the_loop(self, settings):
        import typer

        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("4", "4", "0"),
            patch("media_dl.cli.commands.history.show_history", side_effect=typer.Exit(1)),
            patch("media_dl.ui.pause"),
        ):
            result = CliRunner().invoke(app, ["interactive"])

        assert result.exit_code == 0

    def test_keyboard_interrupt_can_exit(self, settings):
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            patch("media_dl.ui.show_main_menu", side_effect=KeyboardInterrupt),
            patch("media_dl.ui.prompt_yes_no", return_value=True),
        ):
            result = CliRunner().invoke(app, ["interactive"])

        assert result.exit_code == 0
        assert "Hasta luego" in result.output or "Interrumpido" in result.output

    def test_keyboard_interrupt_can_continue(self, settings):
        with (
            patch("media_dl.main.get_settings", return_value=settings),
            _menu("0"),
            patch("media_dl.ui.show_main_menu", side_effect=[KeyboardInterrupt, "0"]),
            patch("media_dl.ui.prompt_yes_no", return_value=False),
        ):
            result = CliRunner().invoke(app, ["interactive"])

        assert result.exit_code == 0


def test_interactive_is_registered():
    result = CliRunner().invoke(app, ["--help"])
    assert "interactive" in result.output


def test_interactive_needs_no_arguments():
    """No debe exigir parámetros: se usa como `media-dl interactive`."""
    import inspect

    signature = inspect.signature(interactive)
    assert not [
        p
        for p in signature.parameters.values()
        if p.default is inspect.Parameter.empty and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
    ]


def test_console_is_bound():
    """Regresión: `console` debe existir a nivel de módulo.

    Antes sólo se definía dentro de la rama `if version:` y `main` reventaba
    con UnboundLocalError.
    """
    from rich.console import Console

    import media_dl.main as main_module

    assert isinstance(main_module.console, Console)
    assert callable(main_module.cli_main)
