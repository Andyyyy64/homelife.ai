from __future__ import annotations

import abc
from pathlib import Path


class LLMProvider(abc.ABC):
    """Abstract base for LLM providers (Claude, Gemini, etc.)."""

    @abc.abstractmethod
    def generate_text(self, prompt: str, timeout: int = 120) -> str | None:
        """Generate text from a text-only prompt."""
        ...

    @abc.abstractmethod
    def analyze_images(
        self, prompt: str, image_paths: list[Path], timeout: int = 120,
    ) -> str | None:
        """Generate text from a prompt with image inputs."""
        ...

    def transcribe_audio(self, audio_path: Path, prompt: str) -> str:
        """Transcribe audio to text. Returns empty string if not supported."""
        return ""
