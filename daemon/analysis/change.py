"""Change detection for screen and camera captures using perceptual hashing."""

from __future__ import annotations

import logging

import cv2
import numpy as np
from pathlib import Path

log = logging.getLogger(__name__)


class ChangeDetector:
    """Detects significant visual changes between consecutive frames.

    Uses a perceptual hash (downscaled grayscale) to compare images.
    Only triggers when the mean pixel difference exceeds a threshold.
    """

    def __init__(self, threshold: float = 0.12):
        self._threshold = threshold
        self._last_hash: np.ndarray | None = None

    def is_changed(self, image: np.ndarray) -> bool:
        """Check if a BGR image differs significantly from the last one seen.

        Returns True on the first call (no baseline) or when change > threshold.
        """
        current = self._compute_hash(image)
        if self._last_hash is None:
            self._last_hash = current
            return True

        diff = float(np.mean(np.abs(current - self._last_hash)))
        if diff > self._threshold:
            self._last_hash = current
            return True
        return False

    def is_changed_file(self, path: Path) -> bool:
        """Check if an image file differs significantly from the last one seen."""
        img = cv2.imread(str(path))
        if img is None:
            return False
        return self.is_changed(img)

    def reset(self) -> None:
        """Clear baseline — next call to is_changed will always return True."""
        self._last_hash = None

    @staticmethod
    def _compute_hash(image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (16, 16), interpolation=cv2.INTER_AREA)
        return small.flatten().astype(np.float32) / 255.0
