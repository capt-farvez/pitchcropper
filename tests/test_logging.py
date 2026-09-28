"""Logs must be machine-readable, carry the run id, and show progress and outcome."""

import json
import logging

from engine.analyzer import FieldBoundaryAnalyzer
from engine.config import PipelineConfig
from engine.detectors import build_detector
from engine.logging_setup import JsonFormatter, RunIdFilter, TextFormatter, configure_logging
from tests.conftest import VALID_CONFIG


def test_formatter_emits_one_json_object_with_extras():
    record = logging.makeLogRecord({"name": "engine.x", "levelname": "INFO", "msg": "run.start", "frame_count": 7})
    RunIdFilter("abc123").filter(record)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["event"] == "run.start"
    assert payload["level"] == "INFO"
    assert payload["run_id"] == "abc123"
    assert payload["frame_count"] == 7
    assert "ts" in payload


def test_text_formatter_is_one_readable_line():
    record = logging.makeLogRecord({"name": "engine.x", "levelname": "INFO", "msg": "run.progress", "percent": 41.7})
    RunIdFilter("abc123").filter(record)
    line = TextFormatter().format(record)
    assert "\n" not in line
    assert "INFO" in line and "run.progress" in line and "percent=41.7" in line
    assert "abc123" not in line  # run id is noise on every line for a human; it stays in json


def test_configure_logging_text_mode(capsys):
    configure_logging("INFO", "run-t", "text")
    logging.getLogger("engine.test").info("hello", extra={"n": 1})
    out = capsys.readouterr().out.strip()
    assert out.endswith("hello              n=1")


def test_configure_logging_writes_json_lines_to_stdout(capsys):
    configure_logging("INFO", "run-1")
    logging.getLogger("engine.test").info("hello", extra={"n": 1})
    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert lines == [dict(lines[0], event="hello", run_id="run-1", n=1)]


def test_run_emits_start_progress_and_done(make_video, capsys):
    video = make_video(60)
    cfg = PipelineConfig.model_validate(
        {
            **VALID_CONFIG,
            "video_path": video,
            "sampling": {"analysis_fps": 30, "max_frames": None, "downscale": 1},
            "logging": {"level": "INFO", "format": "json", "progress_every": 20},
        }
    )
    configure_logging("INFO", "run-2")
    FieldBoundaryAnalyzer(cfg, build_detector(cfg.field_detector)).process_video(video)

    events = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    names = [e["event"] for e in events]
    assert names[0] == "run.start"
    assert names.count("run.progress") == 3  # 60 frames / every 20
    assert names[-1] == "run.done"
    assert all(e["run_id"] == "run-2" for e in events)
    done = events[-1]
    assert done["inspected"] == 60
    assert done["elapsed_s"] >= 0
