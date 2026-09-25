"""Tests for download strategies."""

from unittest.mock import patch

import pytest

from media_dl.config import Settings
from media_dl.core.exceptions import StrategyError
from media_dl.core.strategies import (
    Aria2cStrategy,
    NativeStrategy,
    StrategyFactory,
    build_strategy_args,
)


class TestAria2cStrategy:
    def test_name_and_requires_external(self):
        strategy = Aria2cStrategy()
        assert strategy.name == "aria2c"
        assert strategy.requires_external is True

    def test_is_available_with_aria2c(self):
        strategy = Aria2cStrategy()
        with patch("shutil.which", return_value="/usr/bin/aria2c"):
            assert strategy.is_available() is True

    def test_is_available_without_aria2c(self):
        strategy = Aria2cStrategy()
        with patch("shutil.which", return_value=None):
            assert strategy.is_available() is False

    def test_build_args(self):
        strategy = Aria2cStrategy()
        settings = Settings(
            aria2c_connections=16,
            aria2c_split=16,
            max_download_speed=0,
        )
        args = strategy.build_args(settings)

        assert "external_downloader" in args
        assert args["external_downloader"] == "aria2c"
        assert "external_downloader_args" in args
        assert "aria2c" in args["external_downloader_args"]

        aria2c_args = args["external_downloader_args"]["aria2c"]
        assert "-x16" in aria2c_args
        assert "-s16" in aria2c_args

    def test_build_args_with_speed_limit(self):
        strategy = Aria2cStrategy()
        settings = Settings(
            aria2c_connections=8,
            aria2c_split=8,
            max_download_speed=1000,  # 1000 KB/s
        )
        args = strategy.build_args(settings)
        aria2c_args = args["external_downloader_args"]["aria2c"]
        assert "--max-download-limit=1000K" in aria2c_args

    def test_display_name(self):
        strategy = Aria2cStrategy()
        settings = Settings(aria2c_connections=16)
        name = strategy.get_display_name(settings)
        assert "ULTRA RÁPIDO" in name
        assert "16 hilos" in name


class TestNativeStrategy:
    def test_name_and_requires_external(self):
        strategy = NativeStrategy()
        assert strategy.name == "native"
        assert strategy.requires_external is False

    def test_is_available(self):
        strategy = NativeStrategy()
        assert strategy.is_available() is True

    def test_build_args(self):
        strategy = NativeStrategy()
        settings = Settings()
        args = strategy.build_args(settings)
        assert args == {}

    def test_display_name(self):
        strategy = NativeStrategy()
        name = strategy.get_display_name()
        assert "Normal" in name


class TestStrategyFactory:
    def setup_method(self):
        # Reset factory
        StrategyFactory._strategies.clear()

    def test_register_and_get(self):
        strategy = Aria2cStrategy()
        StrategyFactory.register(strategy)

        retrieved = StrategyFactory.get("aria2c")
        assert retrieved is strategy

    def test_get_unknown(self):
        with pytest.raises(StrategyError):
            StrategyFactory.get("unknown")

    def test_get_best_available_ultra_with_aria2c(self):
        StrategyFactory.register(Aria2cStrategy())
        StrategyFactory.register(NativeStrategy())

        settings = Settings(download_mode="ultra")
        with patch("shutil.which", return_value="/usr/bin/aria2c"):
            strategy = StrategyFactory.get_best_available(settings)
            assert isinstance(strategy, Aria2cStrategy)

    def test_get_best_available_ultra_without_aria2c(self):
        StrategyFactory.register(Aria2cStrategy())
        StrategyFactory.register(NativeStrategy())

        settings = Settings(download_mode="ultra")
        with patch("shutil.which", return_value=None):
            strategy = StrategyFactory.get_best_available(settings)
            assert isinstance(strategy, NativeStrategy)

    def test_get_best_available_normal(self):
        StrategyFactory.register(Aria2cStrategy())
        StrategyFactory.register(NativeStrategy())

        settings = Settings(download_mode="normal")
        strategy = StrategyFactory.get_best_available(settings)
        assert isinstance(strategy, NativeStrategy)


class TestBuildStrategyArgs:
    def test_includes_embed_thumbnail(self):
        strategy = NativeStrategy()
        settings = Settings(embed_thumbnail=True, embed_metadata=True)
        args = build_strategy_args(strategy, settings)

        postprocessors = args.get("postprocessors", [])
        assert any(p.get("key") == "EmbedThumbnail" for p in postprocessors)
        assert any(p.get("key") == "FFmpegMetadata" for p in postprocessors)

    def test_includes_write_info_json(self):
        strategy = NativeStrategy()
        settings = Settings(write_info_json=True)
        args = build_strategy_args(strategy, settings)

        assert args.get("writeinfojson") is True
