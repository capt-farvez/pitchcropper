"""The detector is the swappable seam: the analyzer must work with any FieldDetector."""

import numpy as np
import pytest

from engine.analyzer import FieldBoundaryAnalyzer
from engine.config import DetectorConfig, PipelineConfig
from engine.detectors import HsvMaskDetector, build_detector
from engine.errors import ConfigError
from synthetic_generator import generate_synthetic_video

GREEN_BGR = (34, 139, 34)


def detector_config(**overrides) -> DetectorConfig:
    data = {"type": "hsv_mask", "sport": "football", "min_area": 1000, **overrides}
    return DetectorConfig.model_validate(data)


def pipeline_config(video_path: str) -> PipelineConfig:
    return PipelineConfig.model_validate(
        {
            "video_path": video_path,
            "target_fps": 30,
            "confidence_threshold": 0.5,
            "field_detector": {"type": "hsv_mask", "sport": "football", "min_area": 1000},
            "crop_search": {"aspect_ratio": "16:9", "padding_px": 20},
            "debug_mode": False,
        }
    )


def test_build_detector_returns_registered_implementation():
    detector = build_detector(detector_config())
    assert isinstance(detector, HsvMaskDetector)
    assert detector.name == "hsv_mask"


def test_build_detector_rejects_unregistered_type():
    cfg = detector_config()
    object.__setattr__(cfg, "type", "not_a_detector")  # bypass pydantic to reach the registry check
    with pytest.raises(ConfigError, match="unknown field_detector.type"):
        build_detector(cfg)


def test_hsv_detector_marks_green_as_field():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    frame[:, :5] = GREEN_BGR
    mask = HsvMaskDetector(detector_config()).detect(frame)
    assert mask.shape == (10, 10)
    assert mask[:, :5].all() and not mask[:, 5:].any()


class NeverDetects:
    """A stand-in detector that finds no field anywhere."""

    name = "never"

    def detect(self, frame):
        return np.zeros(frame.shape[:2], dtype=np.uint8)


class RefusesToDetect:
    """A stand-in detector that returns None for every frame."""

    name = "refuses"

    def detect(self, frame):
        return None


@pytest.fixture(scope="module")
def short_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("video") / "short.mp4"
    generate_synthetic_video(str(path), numFrames=30)
    return str(path)


def test_analyzer_uses_whatever_detector_it_is_given(short_video):
    cfg = pipeline_config(short_video)

    with_real = FieldBoundaryAnalyzer(cfg, build_detector(cfg.field_detector)).process_video(short_video)
    with_none = FieldBoundaryAnalyzer(cfg, NeverDetects()).process_video(short_video)
    with_refusal = FieldBoundaryAnalyzer(cfg, RefusesToDetect()).process_video(short_video)

    assert len(with_real) > 0
    assert with_none == []
    assert with_refusal == []
