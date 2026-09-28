"""Field boundary analysis.

Walks the sampled frames of a video, asks the detector for a field mask per
frame, derives a boundary polygon from that mask and records a spatial metric
for it. The analyzer does not know which detector it is given; that is the
seam that varies by sport and deployment. Error handling and aggregation
follow in later commits.
"""

import cv2

from engine.config import PipelineConfig
from engine.detectors.base import FieldDetector
from engine.geometry import frame_bounds, polygon_from_mask, upscale
from engine.sampling import compute_stride, iter_sampled_frames, probe_video


class FieldBoundaryAnalyzer:
    def __init__(self, config: PipelineConfig, detector: FieldDetector):
        self.config = config
        self.detector = detector
        self.threshold = config.confidence_threshold
        self.min_area = config.field_detector.min_area
        self.sampling = config.sampling

    def process_video(self, video_path: str):
        print(f"Starting processing for video: {video_path}")
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            print("Error: Could not open video stream.")
            return

        info = probe_video(cap)
        stride = compute_stride(info.fps, self.sampling.analysis_fps)
        bounds = frame_bounds(info.width, info.height)

        # Detection runs on a shrunken frame when downscale > 1. Areas shrink by
        # the square of the factor, so the threshold is scaled to match, and the
        # resulting polygon is mapped back to full-resolution coordinates.
        factor = self.sampling.downscale
        small_size = (info.width // factor, info.height // factor)
        min_area_small = self.min_area / (factor * factor)

        inspected = 0
        detected_polygons = []

        for index, frame in iter_sampled_frames(cap, stride, self.sampling.max_frames):
            inspected += 1

            if factor > 1:
                frame = cv2.resize(frame, small_size, interpolation=cv2.INTER_AREA)

            mask = self.detector.detect(frame)
            poly = polygon_from_mask(mask, min_area_small) if mask is not None else None

            if poly and poly.is_valid:
                poly = upscale(poly, factor)
                intersection_area = poly.intersection(bounds).area
                detected_polygons.append((index, poly, intersection_area))

        cap.release()
        print(
            f"Inspected {inspected} of {info.frame_count} frames "
            f"(stride {stride}, {info.fps:g} fps source). Found {len(detected_polygons)} boundaries."
        )
        return detected_polygons
