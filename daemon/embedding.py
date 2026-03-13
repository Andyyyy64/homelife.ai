from __future__ import annotations

import logging
import os
from pathlib import Path

from daemon.llm.base import retry_on_transient_error
from daemon.storage.models import ChatMessage, Frame, Summary

log = logging.getLogger(__name__)


class Embedder:
    """Multimodal embedder using Gemini Embedding 2.

    Embeds camera images, screen captures, audio, and text metadata
    into a single unified vector space per frame.
    """

    def __init__(self, model: str = "gemini-embedding-2-preview", dimensions: int = 768):
        self._model = model
        self._dimensions = dimensions
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            log.error("GEMINI_API_KEY not set — embedding disabled")
            return None

        try:
            from google import genai

            self._client = genai.Client(api_key=api_key)
            log.info("Embedding client initialized (model=%s, dims=%d)", self._model, self._dimensions)
            return self._client
        except Exception:
            log.exception("Failed to initialize embedding client")
            return None

    def embed_frame(self, frame: Frame, data_dir: Path) -> list[float] | None:
        """Generate a multimodal embedding for a single frame.

        Combines camera image, screen capture, audio, and text metadata
        into one aggregated embedding via Gemini Embedding 2.

        Returns the embedding vector, or None on failure.
        """
        client = self._get_client()
        if not client:
            return None

        from google.genai import types

        parts: list = []
        image_count = 0

        # Camera image
        if frame.path:
            img_path = data_dir / frame.path
            if img_path.exists():
                parts.append(
                    types.Part.from_bytes(
                        data=img_path.read_bytes(),
                        mime_type="image/jpeg",
                    )
                )
                image_count += 1

        # Screen capture (main)
        if frame.screen_path:
            screen_path = data_dir / frame.screen_path
            if screen_path.exists():
                parts.append(
                    types.Part.from_bytes(
                        data=screen_path.read_bytes(),
                        mime_type="image/png",
                    )
                )
                image_count += 1

        # Audio
        if frame.audio_path:
            audio_path = data_dir / frame.audio_path
            if audio_path.exists():
                parts.append(
                    types.Part.from_bytes(
                        data=audio_path.read_bytes(),
                        mime_type="audio/wav",
                    )
                )

        # Text metadata (description, activity, transcription, window)
        text_parts: list[str] = []
        if frame.claude_description:
            text_parts.append(frame.claude_description)
        if frame.activity:
            text_parts.append(f"Activity: {frame.activity}")
        if frame.transcription:
            text_parts.append(f"Transcription: {frame.transcription}")
        if frame.foreground_window:
            text_parts.append(f"Window: {frame.foreground_window}")

        if text_parts:
            parts.append(types.Part(text="\n".join(text_parts)))

        if not parts:
            log.debug("No content to embed for frame %s", frame.id)
            return None

        try:
            embedding = self._embed_with_retry(client, parts)
            log.info(
                "Embedded frame %s (%d images, audio=%s, text=%s) → %d dims",
                frame.id,
                image_count,
                "yes" if frame.audio_path else "no",
                "yes" if text_parts else "no",
                len(embedding),
            )
            return embedding
        except Exception:
            log.exception("Embedding failed for frame %s", frame.id)
            return None

    @retry_on_transient_error
    def _embed_with_retry(self, client, parts: list) -> list[float]:
        from google.genai import types

        result = client.models.embed_content(
            model=self._model,
            contents=[types.Content(parts=parts)],
            config=types.EmbedContentConfig(
                output_dimensionality=self._dimensions,
                task_type="RETRIEVAL_DOCUMENT",
            ),
        )
        return result.embeddings[0].values

    def embed_chat_message(self, msg: ChatMessage) -> list[float] | None:
        """Embed a chat message (text only).

        Includes channel context and author for richer semantics.
        """
        if not msg.content:
            return None

        parts: list[str] = []
        if msg.channel_name:
            parts.append(f"[{msg.platform}/{msg.channel_name}]")
        if msg.author_name:
            parts.append(f"{msg.author_name}:")
        parts.append(msg.content)
        text = " ".join(parts)

        return self._embed_document_text(text)

    def embed_summary(self, summary: Summary) -> list[float] | None:
        """Embed a summary (text only).

        Includes scale context for temporal semantics.
        """
        if not summary.content:
            return None

        text = f"[{summary.scale} summary] {summary.content}"
        return self._embed_document_text(text)

    def _embed_document_text(self, text: str) -> list[float] | None:
        """Embed text as a document (RETRIEVAL_DOCUMENT task type)."""
        client = self._get_client()
        if not client:
            return None

        try:
            return self._embed_doc_text_with_retry(client, text)
        except Exception:
            log.exception("Document text embedding failed")
            return None

    @retry_on_transient_error
    def _embed_doc_text_with_retry(self, client, text: str) -> list[float]:
        from google.genai import types

        result = client.models.embed_content(
            model=self._model,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=self._dimensions,
                task_type="RETRIEVAL_DOCUMENT",
            ),
        )
        return result.embeddings[0].values

    def embed_text(self, text: str) -> list[float] | None:
        """Embed a text query (for similarity search)."""
        client = self._get_client()
        if not client:
            return None

        try:
            return self._embed_text_with_retry(client, text)
        except Exception:
            log.exception("Text embedding failed")
            return None

    @retry_on_transient_error
    def _embed_text_with_retry(self, client, text: str) -> list[float]:
        from google.genai import types

        result = client.models.embed_content(
            model=self._model,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=self._dimensions,
                task_type="RETRIEVAL_QUERY",
            ),
        )
        return result.embeddings[0].values
