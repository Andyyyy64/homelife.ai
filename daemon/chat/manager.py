"""Chat manager — orchestrates chat platform adapters."""

from __future__ import annotations

import logging
from pathlib import Path

from daemon.chat.base import ChatSource
from daemon.chat.discord import DiscordSource
from daemon.config import ChatConfig

log = logging.getLogger(__name__)


class ChatManager:
    """Creates and manages chat source adapters based on config.

    Each enabled platform gets its own ChatSource that runs in a
    background thread, collecting messages into the shared database.
    """

    def __init__(self, db_path: Path, config: ChatConfig):
        self._sources: list[ChatSource] = []

        if not config.enabled:
            return

        if config.discord.enabled and config.discord.user_token:
            self._sources.append(DiscordSource(db_path, config.discord))
            log.info("Chat source registered: discord")

        # Future adapters:
        # if config.line.enabled:
        #     self._sources.append(LineSource(db_path, config.line))
        # if config.slack.enabled:
        #     self._sources.append(SlackSource(db_path, config.slack))

    def start(self) -> None:
        """Start all registered chat sources."""
        for source in self._sources:
            try:
                source.start()
            except Exception:
                log.exception("Failed to start chat source: %s", source.platform)

    def stop(self) -> None:
        """Stop all running chat sources."""
        for source in self._sources:
            try:
                source.stop()
            except Exception:
                log.exception("Error stopping chat source: %s", source.platform)

    @property
    def active_sources(self) -> list[str]:
        """List of currently running platform names."""
        return [s.platform for s in self._sources if s.is_running()]
