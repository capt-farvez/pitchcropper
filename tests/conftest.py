"""Shared fixtures: a valid config dict and short generated videos."""

import pytest

from synthetic_generator import generate_synthetic_video

VALID_CONFIG = {
    "video_path": "feed.mp4",
    "confidence_threshold": 0.5,
    "sampling": {"analysis_fps": 2, "max_frames": None, "downscale": 1},
    "field_detector": {"type": "hsv_mask", "sport": "football", "min_area": 1000},
    "crop_search": {"aspect_ratio": "16:9", "padding_px": 20},
    "debug_mode": True,
}


@pytest.fixture(scope="session")
def make_video(tmp_path_factory):
    """Return a function that writes a synthetic video with the given number of frames at 30 fps."""

    def _make(num_frames: int) -> str:
        path = tmp_path_factory.mktemp("video") / f"feed_{num_frames}.mp4"
        generate_synthetic_video(str(path), numFrames=num_frames)
        return str(path)

    return _make
