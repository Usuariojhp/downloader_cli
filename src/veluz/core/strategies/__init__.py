"""Strategies package exports."""

from veluz.core.strategies.aria2c import Aria2cStrategy
from veluz.core.strategies.base import (
    DownloadStrategy,
    StrategyFactory,
    build_strategy_args,
)
from veluz.core.strategies.native import NativeStrategy

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
