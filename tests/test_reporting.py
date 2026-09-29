"""Payloads are validated models, sent over HTTP, and a dead service does not raise into the pipeline."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import yaml
from pydantic import ValidationError

from engine.__main__ import main
from engine.aggregate import RunSummary
from engine.reporting import HttpReporter, JobEvent, ProgressReport
from tests.conftest import VALID_CONFIG


class FakeApi:
    """Minimal stand-in for mock_api that records what it receives."""

    def __init__(self):
        self.received: list[tuple[str, dict]] = []
        self.server = HTTPServer(("127.0.0.1", 0), self._make_handler())
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _make_handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                outer.received.append((self.path, json.loads(self.rfile.read(length))))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"received"}')

            def log_message(self, *args):
                pass

        return Handler

    def close(self):
        self.server.shutdown()


@pytest.fixture
def api():
    fake = FakeApi()
    yield fake
    fake.close()


def test_wire_models_reject_unknown_fields():
    with pytest.raises(ValidationError):
        ProgressReport(job_id="j", run_id="r", frame_index=0, inspected=1, expected_inspected=1, percent=100, valid=1, rejected=0, extra=1)
    with pytest.raises(ValidationError):
        JobEvent(job_id="j", run_id="r", event="started", surprise="x")


def test_wire_models_reject_bad_values():
    with pytest.raises(ValidationError):
        JobEvent(job_id="j", run_id="r", event="exploded")
    with pytest.raises(ValidationError):
        ProgressReport(job_id="j", run_id="r", frame_index=-1, inspected=1, expected_inspected=1, percent=100, valid=1, rejected=0)


def test_http_reporter_posts_models_as_json(api):
    reporter = HttpReporter(api.url, job_id="job-1", run_id="run-1", timeout_s=1.0)
    reporter.event(JobEvent(job_id="job-1", run_id="run-1", event="started"))
    reporter.progress(ProgressReport(job_id="job-1", run_id="run-1", frame_index=15, inspected=2, expected_inspected=4, percent=50, valid=2, rejected=0))

    assert reporter.sent == 2 and reporter.failures == 0
    (path1, body1), (path2, body2) = api.received
    assert path1 == "/api/v1/jobs/events" and body1["event"] == "started" and body1["job_id"] == "job-1"
    assert path2 == "/api/v1/jobs/progress" and body2["percent"] == 50 and "timestamp" in body2


def test_unreachable_service_is_counted_not_raised(capsys):
    from engine.logging_setup import configure_logging

    configure_logging("INFO", "r")
    reporter = HttpReporter("http://127.0.0.1:1", job_id="j", run_id="r", timeout_s=0.2)  # nothing listens on port 1
    reporter.event(JobEvent(job_id="j", run_id="r", event="started"))

    assert reporter.failures == 1 and reporter.sent == 0
    warning = [json.loads(l) for l in capsys.readouterr().out.splitlines()][-1]
    assert warning["event"] == "reporting.failed" and warning["level"] == "WARNING"


def test_full_run_reports_started_progress_and_completed(api, tmp_path, make_video):
    video = make_video(60)
    data = {
        **VALID_CONFIG,
        "video_path": video,
        "sampling": {"analysis_fps": 30, "max_frames": None, "downscale": 1},
        "logging": {"level": "INFO", "format": "json", "progress_every": 20},
        "reporting": {**VALID_CONFIG["reporting"], "enabled": True, "base_url": api.url, "job_id": "job-42"},
    }
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    assert main(["--config", str(cfg_path)]) == 0

    paths = [p for p, _ in api.received]
    assert paths[0] == "/api/v1/jobs/events"
    assert paths.count("/api/v1/jobs/progress") == 3
    assert paths[-1] == "/api/v1/jobs/events"

    started, completed = api.received[0][1], api.received[-1][1]
    assert started["event"] == "started" and started["job_id"] == "job-42"
    assert completed["event"] == "completed"
    assert RunSummary.model_validate(completed["summary"]).inspected == 60
    assert all(body["run_id"] == started["run_id"] for _, body in api.received)
