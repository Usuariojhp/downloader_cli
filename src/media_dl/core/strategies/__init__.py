"""Strategies package exports."""

from media_dl.core.strategies.aria2c import Aria2cStrategy
from media_dl.core.strategies.base import (
    DownloadStrategy,
    StrategyFactory,
    build_strategy_args,
)
from media_dl.core.strategies.native import NativeStrategy

# Register default strategies
StrategyFactory.register(Aria2cStrategy())
StrategyFactory.register(NativeStrategy())

__all__ = [
    "Aria2cStrategy",
    "DownloadStrategy",
    "NativeStrategy",
    "StrategyFactory",
    "build_strategy_args",
]
