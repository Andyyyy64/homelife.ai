from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SceneType(Enum):
    DARK = "dark"
    NORMAL = "normal"
    BRIGHT = "bright"


# Analysis time scales
SCALES = {
    "10m": 600,
    "30m": 1800,
    "1h": 3600,
    "6h": 21600,
    "12h": 43200,
    "24h": 86400,
}


@dataclass
class Frame:
    id: int | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    path: str = ""
    screen_path: str = ""
    audio_path: str = ""
    transcription: str = ""
    brightness: float = 0.0
    motion_score: float = 0.0
    scene_type: SceneType = SceneType.NORMAL
    claude_description: str = ""
    activity: str = ""
    screen_extra_paths: str = ""  # comma-separated extra screen paths
    foreground_window: str = ""  # "process_name|window_title"
    pose_data: str = ""  # JSON from PoseResult
    idle_seconds: int = 0  # seconds since last mouse/keyboard input


@dataclass
class Event:
    id: int | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = ""  # motion_spike, scene_change
    description: str = ""
    frame_id: int | None = None


@dataclass
class Summary:
    id: int | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    scale: str = ""  # 10m, 30m, 1h, 6h, 12h, 24h
    content: str = ""
    frame_count: int = 0


@dataclass
class Report:
    id: int | None = None
    date: str = ""  # YYYY-MM-DD
    content: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    frame_count: int = 0
    focus_pct: float = 0.0


@dataclass
class ChatMessage:
    id: int | None = None
    platform: str = ""  # "discord", "line", "slack", ...
    platform_message_id: str = ""
    channel_id: str = ""
    channel_name: str = ""
    guild_id: str = ""
    guild_name: str = ""
    author_id: str = ""
    author_name: str = ""
    is_self: bool = False
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: str = ""  # JSON for platform-specific extras
