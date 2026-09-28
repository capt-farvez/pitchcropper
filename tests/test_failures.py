"""Which failures stop the run, which are counted and skipped, and none are silent."""

import json

import numpy as np
import pytest
import yaml

from engine.__main__ import main
from engine.analyzer import FieldBoundaryAnalyzer
from engine.config import PipelineConfig
from engine.errors import StreamBrokenError, VideoOpenError
from engine.geometry import polygon_from_mask
from engine.logging_setup import configure_logging
from tests.conftest import VALID_CONFIG


def config_for(video: str, **overrides) -> PipelineConfig:
    data = {
        **VALID_CONFIG,
        "video_path": video,
        "sampling": {"analysis_fps": 30, "max_frames": None, "downscale": 1},
        **overrides,
    }
    return PipelineConfig.model_validate(data)


def events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]


class AlwaysRaises:
    name = "always_raises"

    def detect(self, frame):
        raise RuntimeError("model exploded")


class RaisesOnce:
    name = "raises_once"

    def __init__(self):
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("one bad frame")
        return np.full(frame.shape[:2], 255, dtype=np.uint8)


class BadMaskDtype:
    """Returns a float mask, which findContours rejects. Simulates a misbehaving model."""

    name = "bad_dtype"

    def detect(self, frame):
        return np.ones(frame.shape[:2], dtype=np.float32)


def test_unopenable_video_stops_the_run(tmp_path):
    cfg = config_for(str(tmp_path / "missing.mp4"))
    with pytest.raises(VideoOpenError, match="could not open"):
        FieldBoundaryAnalyzer(cfg, AlwaysRaises()).process_video(cfg.video_path)


def test_one_bad_frame_is_counted_not_fatal(make_video, capsys):
    video = make_video(30)
    cfg = config_for(video)
    configure_logging("INFO", "r")
    detector = RaisesOnce()
    results = FieldBoundaryAnalyzer(cfg, detector).process_video(video)

    done = [e for e in events(capsys) if e["event"] == "run.done"][0]
    assert done["inspected"] == 30
    assert done["rejected"] == {"detect_failed": 1}
    assert results.valid == 29


def test_bad_frame_is_logged_with_traceback(make_video, capsys):
    video = make_video(30)
    cfg = config_for(video)
    configure_logging("INFO", "r")
    FieldBoundaryAnalyzer(cfg, RaisesOnce()).process_video(video)

    warnings = [e for e in events(capsys) if e["event"] == "frame.detect_failed"]
    assert len(warnings) == 1
    assert warnings[0]["level"] == "WARNING"
    assert "one bad frame" in warnings[0]["exception"]


def test_repeated_failures_break_the_stream(make_video, capsys):
    video = make_video(30)
    cfg = config_for(video, resilience={"max_consecutive_frame_errors": 3})
    configure_logging("INFO", "r")
    with pytest.raises(StreamBrokenError, match="3 consecutive frames failed at frame 2"):
        FieldBoundaryAnalyzer(cfg, AlwaysRaises()).process_video(video)

    names = [e["event"] for e in events(capsys)]
    assert names.count("frame.detect_failed") == 3
    assert "run.done" not in names


def test_malformed_mask_is_not_swallowed():
    # the prototype's bare except turned this into "no boundary"; now it raises so the analyzer can count it
    with pytest.raises(Exception):
        polygon_from_mask(np.ones((10, 10), dtype=np.float32), min_area=1)


def test_malformed_mask_from_detector_is_counted(make_video, capsys):
    video = make_video(5)
    cfg = config_for(video)
    configure_logging("INFO", "r")
    summary = FieldBoundaryAnalyzer(cfg, BadMaskDtype()).process_video(video)
    assert summary.rejected["detect_failed"] == 5
    assert summary.valid == 0
    assert summary.boundary is None


def test_main_exits_1_when_video_cannot_be_opened(tmp_path, capsys):
    # a path in a directory that does not exist: the generator cannot write there, so nothing can be opened
    data = {**VALID_CONFIG, "video_path": str(tmp_path / "no_such_dir" / "feed.mp4")}
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    code = main(["--config", str(cfg_path)])

    assert code == 1
    failed = [e for e in events(capsys) if e["event"] == "run.failed"][0]
    assert failed["reason"] == "VideoOpenError"
