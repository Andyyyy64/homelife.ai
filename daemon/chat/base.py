"""Abstract base class for chat platform adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ChatSource(ABC):
    """Abstract interface for chat platform adapters.

    Each adapter connects to a chat platform, collects messages,
    and writes them to the shared database. Adapters run as background
    threads managed by ChatManager.
    """

    @property
    @abstractmethod
    def platform(self) -> str:
        """Platform identifier (e.g. 'discord', 'line', 'slack')."""
        ...

    @abstractmethod
    def start(self) -> None:
        """Start collecting messages in a background thread."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop collecting and clean up resources."""
        ...

    @abstractmethod
    def is_running(self) -> bool:
        """Whether the source is actively collecting."""
        ...
