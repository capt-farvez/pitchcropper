"""Field boundary analysis.

Walks a video, asks the detector for a field mask per frame, derives a
boundary polygon from that mask and records a spatial metric for it. The
analyzer does not know which detector it is given; that is the seam that
varies by sport and deployment. Sampling and error handling follow in
later commits.
"""

import time

import cv2
import numpy as np
from shapely.geometry import Polygon

from engine.config import PipelineConfig
from engine.detectors.base import FieldDetector


class FieldBoundaryAnalyzer:
    def __init__(self, config: PipelineConfig, detector: FieldDetector):
        self.config = config
        self.detector = detector
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

            mask = self.detector.detect(frame)
            poly = self._derive_polygon_from_mask(mask) if mask is not None else None

            if poly and poly.is_valid:
                outer_boundary = Polygon([(0, 0), (1280, 0), (1280, 720), (0, 720)])
                intersection_area = poly.intersection(outer_boundary).area
                detected_polygons.append((frame_count, poly, intersection_area))

            # Simulate heavy per-frame processing latency
            time.sleep(0.005)

        cap.release()
        print(f"Processed {frame_count} frames. Found {len(detected_polygons)} boundaries.")
        return detected_polygons

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
