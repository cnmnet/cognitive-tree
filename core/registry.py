"""Processor registration."""

from __future__ import annotations

from typing import Dict, List

from .interfaces import IProcessor


class ProcessorRegistry:
    def __init__(self) -> None:
        self._processors: Dict[str, IProcessor] = {}

    def register(self, processor: IProcessor) -> None:
        if processor.name in self._processors:
            raise ValueError(f"processor already registered: {processor.name}")
        self._processors[processor.name] = processor

    def get(self, name: str) -> IProcessor:
        if name not in self._processors:
            raise KeyError(f"processor not registered: {name}")
        return self._processors[name]

    def names(self) -> List[str]:
        return sorted(self._processors)

    def __len__(self) -> int:
        return len(self._processors)
