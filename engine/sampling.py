"""Decide which frames to look at, and skip the rest as cheaply as possible.

The prototype decoded and analysed every frame, so a video twice as long took
twice as long. Here the video's frame rate is read once, a stride is derived
from the requested analysis rate, and only every stride-th frame is handed to
the detector. Skipped frames go through cap.grab(), which advances the stream
without the colour conversion and copy that cap.read() does. Detection,
polygon derivation and metrics, the expensive parts, run only on inspected
frames.
"""

from collections.abc import Iterator
from dataclasses import dataclass

import cv2
import numpy as np

from engine.errors import VideoProbeError


@dataclass(frozen=True)
class VideoInfo:
    fps: float
    frame_count: int
    width: int
    height: int


def probe_video(cap: cv2.VideoCapture) -> VideoInfo:
    """Read stream properties once. Raises VideoProbeError if the source reports no usable frame rate."""
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if fps <= 0:
        raise VideoProbeError("video source reports no frame rate; cannot derive a sampling stride")
    return VideoInfo(
        fps=fps,
        frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    )


def compute_stride(source_fps: float, analysis_fps: float) -> int:
    """Inspect one frame in every `stride`. Never less than 1, so asking for more than the source gives every frame."""
    return max(1, round(source_fps / analysis_fps))


def iter_sampled_frames(
    cap: cv2.VideoCapture, stride: int, max_frames: int | None = None
) -> Iterator[tuple[int, np.ndarray | None]]:
    """Yield (frame_index, frame) for every stride-th frame, stopping at end of stream or max_frames.

    A frame that was grabbed but could not be decoded is yielded as None so the
    caller can count it rather than have it vanish.
    """
    index = 0
    inspected = 0
    while max_frames is None or inspected < max_frames:
        if not cap.grab():
            break
        if index % stride == 0:
            ok, frame = cap.retrieve()
            inspected += 1
            yield index, (frame if ok else None)
        index += 1
