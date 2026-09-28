"""Colour-threshold field detector.

Stands in for a real segmentation model. Marks green pixels in HSV space as
field. The thresholds are built once in the constructor instead of on every
frame as the prototype did.
"""

import cv2
import numpy as np

from engine.config import DetectorConfig


class HsvMaskDetector:
    name = "hsv_mask"

    def __init__(self, config: DetectorConfig):
        self.sport = config.sport
        self._lower = np.array([35, 40, 40], dtype=np.uint8)
        self._upper = np.array([85, 255, 255], dtype=np.uint8)

    def detect(self, frame: np.ndarray) -> np.ndarray | None:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        return cv2.inRange(hsv, self._lower, self._upper)
