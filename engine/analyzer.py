"""Field boundary analysis.

Walks the sampled frames of a video, asks the detector for a field mask per
frame, derives a boundary polygon from that mask and records a spatial metric
for it. The analyzer does not know which detector it is given; that is the
seam that varies by sport and deployment. Failure classification and
aggregation follow in later commits.
"""

import logging
import time

import cv2

from engine.config import PipelineConfig
from engine.detectors.base import FieldDetector
from engine.geometry import frame_bounds, polygon_from_mask, upscale
from engine.sampling import compute_stride, iter_sampled_frames, probe_video

log = logging.getLogger("engine.analyzer")


class FieldBoundaryAnalyzer:
    def __init__(self, config: PipelineConfig, detector: FieldDetector):
        self.config = config
        self.detector = detector
        self.threshold = config.confidence_threshold
        self.min_area = config.field_detector.min_area
        self.sampling = config.sampling
        self.progress_every = config.logging.progress_every

    def process_video(self, video_path: str):
        started = time.perf_counter()
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            log.error("video.open_failed", extra={"video_path": video_path})
            return

        info = probe_video(cap)
        stride = compute_stride(info.fps, self.sampling.analysis_fps)
        bounds = frame_bounds(info.width, info.height)
        expected = info.frame_count // stride + (1 if info.frame_count % stride else 0)
        if self.sampling.max_frames is not None:
            expected = min(expected, self.sampling.max_frames)

        log.info(
            "run.start",
            extra={
                "video_path": video_path,
                "detector": self.detector.name,
                "source_fps": info.fps,
                "frame_count": info.frame_count,
                "size": [info.width, info.height],
                "stride": stride,
                "expected_inspected": expected,
            },
        )

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
            else:
                log.debug("frame.no_boundary", extra={"frame_index": index})

            if inspected % self.progress_every == 0:
                elapsed = time.perf_counter() - started
                log.info(
                    "run.progress",
                    extra={
                        "frame_index": index,
                        "inspected": inspected,
                        "expected_inspected": expected,
                        "percent": round(100 * inspected / expected, 1) if expected else None,
                        "found": len(detected_polygons),
                        "elapsed_s": round(elapsed, 2),
                        "eta_s": round(elapsed / inspected * (expected - inspected), 1) if expected else None,
                    },
                )

        cap.release()
        elapsed = time.perf_counter() - started
        log.info(
            "run.done",
            extra={
                "inspected": inspected,
                "frame_count": info.frame_count,
                "found": len(detected_polygons),
                "elapsed_s": round(elapsed, 2),
                "inspected_per_s": round(inspected / elapsed, 1) if elapsed else None,
            },
        )
        return detected_polygons
