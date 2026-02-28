"""Discord chat source — collects messages via REST API polling with user token."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from daemon.chat.base import ChatSource
from daemon.config import DiscordChatConfig

log = logging.getLogger(__name__)

API_BASE = "https://discord.com/api/v10"
# Only collect text-based channel types
# 0=GUILD_TEXT, 5=GUILD_ANNOUNCEMENT, 10=ANNOUNCEMENT_THREAD,
# 11=PUBLIC_THREAD, 12=PRIVATE_THREAD
TEXT_CHANNEL_TYPES = {0, 5, 10, 11, 12}


class DiscordSource(ChatSource):
    """Collects messages from Discord servers and DMs using a user token.

    On first run, backfills historical messages (configurable months).
    Then polls every poll_interval seconds for new messages.
    """

    def __init__(self, db_path: Path, config: DiscordChatConfig):
        self._db_path = db_path
        self._config = config
        self._running = False
        self._thread: threading.Thread | None = None
        # channel_id -> last known platform_message_id
        self._last_ids: dict[str, str] = {}
        # guild_id -> guild_name cache
        self._guild_names: dict[str, str] = {}

    @property
    def platform(self) -> str:
        return "discord"

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="chat-discord",
        )
        self._thread.start()
        log.info("Discord chat source started (poll every %ds)", self._config.poll_interval)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        log.info("Discord chat source stopped")

    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    # --- Internal ---

    def _run(self) -> None:
        """Main loop: backfill once, then poll."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row

        self._load_last_ids(conn)
        log.info("Loaded %d channel positions from DB", len(self._last_ids))

        # One-time historical backfill for channels not yet tracked
        self._backfill(conn)

        while self._running:
            try:
                self._poll_once(conn)
            except Exception:
                log.exception("Discord poll cycle failed")
            for _ in range(self._config.poll_interval):
                if not self._running:
                    break
                time.sleep(1)

        conn.close()

    def _load_last_ids(self, conn: sqlite3.Connection) -> None:
        """Load last known message ID per channel from DB."""
        rows = conn.execute(
            "SELECT channel_id, platform_message_id FROM chat_messages "
            "WHERE platform='discord' AND id IN ("
            "  SELECT MAX(id) FROM chat_messages WHERE platform='discord' GROUP BY channel_id"
            ")"
        ).fetchall()
        self._last_ids = {r["channel_id"]: r["platform_message_id"] for r in rows}

    # --- Backfill ---

    def _backfill(self, conn: sqlite3.Connection) -> None:
        """Backfill historical messages for channels not yet in DB."""
        if self._config.backfill_months <= 0:
            return

        cutoff = datetime.now() - timedelta(days=self._config.backfill_months * 30)
        channels = self._collect_channels()
        # Only backfill channels we haven't seen before
        to_backfill = [(c, n, g, gn) for c, n, g, gn in channels if c not in self._last_ids]

        if not to_backfill:
            log.info("Backfill: all %d channels already tracked", len(channels))
            return

        log.info(
            "Backfilling %d/%d channels (cutoff: %s, %d months)",
            len(to_backfill), len(channels),
            cutoff.strftime("%Y-%m-%d"), self._config.backfill_months,
        )

        total = 0
        for ch_id, ch_name, g_id, g_name in to_backfill:
            if not self._running:
                break
            n = self._backfill_channel(conn, ch_id, ch_name, g_id, g_name, cutoff)
            total += n

        log.info("Backfill complete: %d messages from %d channels", total, len(to_backfill))

    def _collect_channels(self) -> list[tuple[str, str, str, str]]:
        """Collect all accessible channels (DMs + guilds).

        Returns list of (channel_id, channel_name, guild_id, guild_name).
        """
        channels: list[tuple[str, str, str, str]] = []

        dm_channels = self._api_get("/users/@me/channels")
        if dm_channels:
            for ch in dm_channels:
                ch_name = self._resolve_dm_name(ch)
                channels.append((ch["id"], ch_name, "", ""))

        guilds = self._api_get("/users/@me/guilds")
        if guilds:
            for g in guilds:
                g_id = g["id"]
                g_name = g.get("name", "")
                self._guild_names[g_id] = g_name
                guild_channels = self._api_get(f"/guilds/{g_id}/channels")
                if not guild_channels:
                    continue
                for ch in guild_channels:
                    if ch.get("type") not in TEXT_CHANNEL_TYPES:
                        continue
                    channels.append((ch["id"], ch.get("name", ""), g_id, g_name))

        return channels

    def _backfill_channel(
        self, conn: sqlite3.Connection,
        channel_id: str, channel_name: str,
        guild_id: str, guild_name: str,
        cutoff: datetime,
    ) -> int:
        """Paginate backwards through a channel's history until cutoff. Returns count."""
        before_id: str | None = None
        total = 0
        newest_id: str | None = None

        while self._running:
            params = "limit=100"
            if before_id:
                params += f"&before={before_id}"

            messages = self._api_get(f"/channels/{channel_id}/messages?{params}")
            if not messages:
                break

            reached_cutoff = False
            for msg in messages:  # newest to oldest
                if newest_id is None:
                    newest_id = msg["id"]

                ts = self._parse_timestamp(msg["timestamp"])
                if ts < cutoff:
                    reached_cutoff = True
                    break

                n = self._store_message(conn, msg, channel_id, channel_name, guild_id, guild_name)
                total += n
                before_id = msg["id"]

            conn.commit()

            if reached_cutoff or len(messages) < 100:
                break

            # Rate-limit: be gentle during backfill
            time.sleep(1)

        # Track newest message for future polls
        if newest_id:
            existing = self._last_ids.get(channel_id)
            if not existing or self._id_cmp(newest_id, existing) > 0:
                self._last_ids[channel_id] = newest_id

        label = f"{guild_name}/{channel_name}" if guild_name else channel_name
        if total > 0:
            log.info("Backfill %s: %d messages", label, total)

        return total

    # --- Polling ---

    def _poll_once(self, conn: sqlite3.Connection) -> None:
        """Run one poll cycle: DMs then guilds."""
        count = 0

        # 1. DM channels
        dm_channels = self._api_get("/users/@me/channels")
        if dm_channels:
            for ch in dm_channels:
                ch_id = ch["id"]
                remote_last = ch.get("last_message_id")
                if not remote_last:
                    continue
                local_last = self._last_ids.get(ch_id)
                if local_last and self._id_cmp(remote_last, local_last) <= 0:
                    continue
                ch_name = self._resolve_dm_name(ch)
                n = self._fetch_new_messages(conn, ch_id, ch_name, "", "")
                count += n

        # 2. Guild channels
        guilds = self._api_get("/users/@me/guilds")
        if guilds:
            for g in guilds:
                g_id = g["id"]
                g_name = g.get("name", "")
                self._guild_names[g_id] = g_name
                channels = self._api_get(f"/guilds/{g_id}/channels")
                if not channels:
                    continue
                for ch in channels:
                    if ch.get("type") not in TEXT_CHANNEL_TYPES:
                        continue
                    ch_id = ch["id"]
                    remote_last = ch.get("last_message_id")
                    if not remote_last:
                        continue
                    local_last = self._last_ids.get(ch_id)
                    if local_last and self._id_cmp(remote_last, local_last) <= 0:
                        continue
                    ch_name = ch.get("name", "")
                    n = self._fetch_new_messages(conn, ch_id, ch_name, g_id, g_name)
                    count += n

        if count > 0:
            log.info("Discord: collected %d new messages", count)

    def _fetch_new_messages(
        self, conn: sqlite3.Connection,
        channel_id: str, channel_name: str,
        guild_id: str, guild_name: str,
    ) -> int:
        """Fetch messages newer than last known ID. Returns count."""
        last_id = self._last_ids.get(channel_id)
        params = "limit=100"
        if last_id:
            params += f"&after={last_id}"

        messages = self._api_get(f"/channels/{channel_id}/messages?{params}")
        if not messages:
            return 0

        count = 0
        # Discord returns newest first, reverse for chronological insert
        for msg in reversed(messages):
            n = self._store_message(conn, msg, channel_id, channel_name, guild_id, guild_name)
            count += n
            self._last_ids[channel_id] = msg["id"]

        if count > 0:
            conn.commit()
        return count

    # --- Shared helpers ---

    def _store_message(
        self, conn: sqlite3.Connection,
        msg: dict, channel_id: str, channel_name: str,
        guild_id: str, guild_name: str,
    ) -> int:
        """Store a single Discord message. Returns 1 on success, 0 on skip/duplicate."""
        # Skip non-default message types (joins, pins, system messages)
        if msg.get("type", 0) not in (0, 19):  # DEFAULT, REPLY
            return 0
        if not msg.get("content") and not msg.get("attachments"):
            return 0

        author = msg.get("author", {})
        ts = self._parse_timestamp(msg["timestamp"])

        attachments = [a.get("filename", "") for a in msg.get("attachments", [])]
        meta = json.dumps(
            {"attachments": attachments, "embeds": len(msg.get("embeds", []))},
            ensure_ascii=False,
        ) if attachments or msg.get("embeds") else ""

        try:
            conn.execute(
                "INSERT INTO chat_messages "
                "(platform, platform_message_id, channel_id, channel_name, "
                "guild_id, guild_name, author_id, author_name, is_self, "
                "content, timestamp, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "discord", msg["id"], channel_id, channel_name,
                    guild_id, guild_name,
                    author.get("id", ""),
                    author.get("global_name") or author.get("username", ""),
                    author.get("id") == self._config.user_id,
                    msg.get("content", ""),
                    ts.isoformat(),
                    meta,
                ),
            )
            return 1
        except sqlite3.IntegrityError:
            return 0  # duplicate

    def _api_get(self, path: str) -> list | dict | None:
        """Make a GET request to Discord API. Returns parsed JSON or None on error."""
        url = f"{API_BASE}{path}"
        req = urllib.request.Request(url, headers={
            "Authorization": self._config.user_token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                try:
                    body = json.loads(e.read())
                    retry_after = body.get("retry_after", 5)
                except Exception:
                    retry_after = 5
                log.warning("Discord rate limited, sleeping %.1fs", retry_after)
                time.sleep(retry_after)
                return None
            elif e.code == 403:
                return None
            else:
                log.warning("Discord API %d: %s %s", e.code, path, e.reason)
                return None
        except Exception:
            log.exception("Discord API request failed: %s", path)
            return None

    @staticmethod
    def _resolve_dm_name(channel: dict) -> str:
        """Resolve a human-readable name for a DM channel."""
        recipients = channel.get("recipients", [])
        ch_type = channel.get("type")
        if ch_type == 1:  # DM
            if recipients:
                r = recipients[0]
                return r.get("global_name") or r.get("username", "DM")
            return "DM"
        elif ch_type == 3:  # Group DM
            if channel.get("name"):
                return channel["name"]
            names = [r.get("global_name") or r.get("username", "?") for r in recipients]
            return ", ".join(names[:4])
        return "unknown"

    @staticmethod
    def _parse_timestamp(ts_str: str) -> datetime:
        """Parse Discord ISO timestamp to local naive datetime."""
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt

    @staticmethod
    def _id_cmp(a: str, b: str) -> int:
        """Compare Discord snowflake IDs numerically."""
        try:
            ia, ib = int(a), int(b)
            return (ia > ib) - (ia < ib)
        except ValueError:
            return (a > b) - (a < b)
