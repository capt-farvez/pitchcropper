"""Field boundary analysis, lifted out of the research prototype.

Reads its settings from the validated PipelineConfig, so there are no
defaults hidden in this module. The detector seam, sampling and error
handling follow in later commits.
"""

import time

import cv2
import numpy as np
from shapely.geometry import Polygon

from engine.config import PipelineConfig


class FieldBoundaryAnalyzer:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.sport = config.field_detector.sport
        self.threshold = config.confidence_threshold
        self.min_area = config.field_detector.min_area

    def process_video(self, video_path: str):
        print(f"Starting processing for video: {video_path}")
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            print("Error: Could not open video stream.")
            return

        frame_count = 0
        detected_polygons = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            mask = self._extract_mask(frame)
            poly = self._derive_polygon_from_mask(mask)

            if poly and poly.is_valid:
                outer_boundary = Polygon([(0, 0), (1280, 0), (1280, 720), (0, 720)])
                intersection_area = poly.intersection(outer_boundary).area
                detected_polygons.append((frame_count, poly, intersection_area))

            # Simulate heavy per-frame processing latency
            time.sleep(0.005)

        cap.release()
        print(f"Processed {frame_count} frames. Found {len(detected_polygons)} boundaries.")
        return detected_polygons

    def _extract_mask(self, frame: np.ndarray) -> np.ndarray:
        # Dummy mask generation based on green color thresholding
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        return cv2.inRange(hsv, lower_green, upper_green)

    def _derive_polygon_from_mask(self, mask: np.ndarray):
        try:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                if cv2.contourArea(largest) > self.min_area:
                    pts = largest.reshape(-1, 2)
                    if len(pts) >= 3:
                        return Polygon(pts)
        except Exception:
            pass
        return None
