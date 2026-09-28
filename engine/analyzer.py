"""Field boundary analysis.

Walks the sampled frames of a video, asks the detector for a field mask per
frame, derives a boundary polygon from that mask and hands it to the
aggregator, which decides whether it counts. The analyzer does not know which
detector it is given; that is the seam that varies by sport and deployment.

Failure policy:
- Cannot open or probe the video: raise, the run stops (PipelineError).
- One frame fails to decode, or the detector raises on it: log with the
  traceback, count it, continue. Real feeds have bad frames.
- Frames fail like that N times in a row: raise StreamBrokenError. That is no
  longer noise, the stream is gone.
- A frame decodes fine but has no usable boundary: count it with a reason,
  continue. That is a close-up or a cut, not an error.
"""

import logging
import time

import cv2

from engine.aggregate import DetectionAggregator, RejectReason, RunSummary
from engine.config import PipelineConfig
from engine.detectors.base import FieldDetector
from engine.errors import StreamBrokenError, VideoOpenError
from engine.geometry import polygon_from_mask, upscale
from engine.sampling import compute_stride, iter_sampled_frames, probe_video

log = logging.getLogger("engine.analyzer")


class FieldBoundaryAnalyzer:
    def __init__(self, config: PipelineConfig, detector: FieldDetector):
        self.config = config
        self.detector = detector
        self.threshold = config.confidence_threshold
        self.min_area = config.field_detector.min_area
        self.max_coverage = config.field_detector.max_coverage
        self.sampling = config.sampling
        self.progress_every = config.logging.progress_every
        self.max_consecutive_errors = config.resilience.max_consecutive_frame_errors

    def process_video(self, video_path: str) -> RunSummary:
        started = time.perf_counter()
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise VideoOpenError(f"could not open video source: {video_path}")

        try:
            return self._process(cap, video_path, started)
        finally:
            cap.release()

    def _process(self, cap: cv2.VideoCapture, video_path: str, started: float) -> RunSummary:
        info = probe_video(cap)
        stride = compute_stride(info.fps, self.sampling.analysis_fps)
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

        agg = DetectionAggregator(info.width, info.height, self.max_coverage)
        consecutive_errors = 0

        for index, frame in iter_sampled_frames(cap, stride, self.sampling.max_frames):
            if frame is None:
                agg.reject(RejectReason.DECODE_FAILED)
                consecutive_errors += 1
                log.warning("frame.decode_failed", extra={"frame_index": index})
            else:
                try:
                    if factor > 1:
                        frame = cv2.resize(frame, small_size, interpolation=cv2.INTER_AREA)
                    mask = self.detector.detect(frame)
                    poly = polygon_from_mask(mask, min_area_small) if mask is not None else None
                except Exception:
                    agg.reject(RejectReason.DETECT_FAILED)
                    consecutive_errors += 1
                    log.warning("frame.detect_failed", extra={"frame_index": index}, exc_info=True)
                else:
                    consecutive_errors = 0
                    reason = agg.consider(index, upscale(poly, factor) if poly is not None else None)
                    if reason is not None:
                        log.debug("frame.rejected", extra={"frame_index": index, "reason": reason.value})

            if consecutive_errors >= self.max_consecutive_errors:
                raise StreamBrokenError(
                    f"{consecutive_errors} consecutive frames failed at frame {index}; treating the stream as broken"
                )

            if agg.inspected % self.progress_every == 0:
                elapsed = time.perf_counter() - started
                log.info(
                    "run.progress",
                    extra={
                        "frame_index": index,
                        "inspected": agg.inspected,
                        "expected_inspected": expected,
                        "percent": round(100 * agg.inspected / expected, 1) if expected else None,
                        "valid": agg.valid,
                        "rejected": agg.inspected - agg.valid,
                        "elapsed_s": round(elapsed, 2),
                        "eta_s": round(elapsed / agg.inspected * (expected - agg.inspected), 1) if expected else None,
                    },
                )

        summary = agg.summary(info.frame_count)
        elapsed = time.perf_counter() - started
        log.info(
            "run.done",
            extra={
                "inspected": summary.inspected,
                "frame_count": summary.frame_count,
                "valid": summary.valid,
                "rejected": {k.value: v for k, v in summary.rejected.items() if v},
                "coverage_median": summary.coverage["median"] if summary.coverage else None,
                "elapsed_s": round(elapsed, 2),
                "inspected_per_s": round(summary.inspected / elapsed, 1) if elapsed else None,
            },
        )
        return summary
