"""A reporting failure is not a pipeline failure, and a pipeline failure is not hidden by reporting."""

import json

import yaml

from engine.__main__ import main
from engine.logging_setup import configure_logging
from engine.reporting import HttpReporter, JobEvent, ProgressReport
from tests.conftest import VALID_CONFIG
from tests.test_reporting import FakeApi, api  # noqa: F401  (fixture re-export)

DEAD_URL = "http://127.0.0.1:1"  # nothing listens on port 1


def progress(n=1):
    return ProgressReport(job_id="j", run_id="r", frame_index=n, inspected=n, expected_inspected=10, percent=10.0 * n, valid=n, rejected=0)


def events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]


def write_config(tmp_path, **overrides):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump({**VALID_CONFIG, **overrides}), encoding="utf-8")
    return str(path)


def reporting(base_url, **overrides):
    return {**VALID_CONFIG["reporting"], "enabled": True, "base_url": base_url, **overrides}


class FlakyApi(FakeApi):
    """Fails the first `fail_first` requests with a 503, then behaves."""

    def __init__(self, fail_first: int):
        self.remaining_failures = fail_first
        super().__init__()

    def _make_handler(self):
        outer = self
        base = super()._make_handler()

        class Handler(base):
            def do_POST(self):
                if outer.remaining_failures > 0:
                    outer.remaining_failures -= 1
                    self.rfile.read(int(self.headers.get("Content-Length", 0)))
                    self.send_response(503)
                    self.end_headers()
                    return
                super().do_POST()

        return Handler


def test_retries_absorb_a_blip():
    flaky = FlakyApi(fail_first=2)
    try:
        reporter = HttpReporter(flaky.url, "j", "r", timeout_s=1.0, max_retries=2, retry_backoff_s=0.0)
        reporter.progress(progress())
    finally:
        flaky.close()
    assert reporter.sent == 1 and reporter.failures == 0
    assert len(flaky.received) == 1


def test_exhausted_retries_count_one_failure():
    flaky = FlakyApi(fail_first=5)
    try:
        reporter = HttpReporter(flaky.url, "j", "r", timeout_s=1.0, max_retries=1, retry_backoff_s=0.0)
        reporter.progress(progress())
    finally:
        flaky.close()
    assert reporter.sent == 0 and reporter.failures == 1


def test_degrades_after_consecutive_failures_and_stops_sending_progress(capsys):
    configure_logging("INFO", "r")
    reporter = HttpReporter(DEAD_URL, "j", "r", timeout_s=0.2, max_retries=0, max_consecutive_failures=2)
    for n in range(5):
        reporter.progress(progress(n))

    assert reporter.degraded is True
    assert reporter.failures == 2  # only the first two were attempted
    assert reporter.skipped == 3
    names = [e["event"] for e in events(capsys)]
    assert names.count("reporting.failed") == 2
    assert names.count("reporting.degraded") == 1


def test_lifecycle_events_are_still_attempted_when_degraded():
    reporter = HttpReporter(DEAD_URL, "j", "r", timeout_s=0.2, max_retries=0, max_consecutive_failures=1)
    reporter.progress(progress())
    assert reporter.degraded
    reporter.event(JobEvent(job_id="j", run_id="r", event="completed"))
    assert reporter.failures == 2  # the event was tried, and failed, rather than skipped


def test_pipeline_ok_reporting_dead_exits_3(tmp_path, make_video, capsys):
    cfg = write_config(
        tmp_path,
        video_path=make_video(30),
        sampling={"analysis_fps": 30, "max_frames": None, "downscale": 1},
        reporting=reporting(DEAD_URL, timeout_s=0.2),
    )
    assert main(["--config", cfg]) == 3
    finished = [e for e in events(capsys) if e["event"] == "run.finished"][0]
    assert finished["level"] == "WARNING"
    assert finished["reports_failed"] >= 2 and finished["valid"] > 0  # the video work still counted


def test_pipeline_failed_reporting_dead_exits_1(tmp_path, capsys):
    cfg = write_config(
        tmp_path,
        video_path=str(tmp_path / "no_such_dir" / "feed.mp4"),
        reporting=reporting(DEAD_URL, timeout_s=0.2),
    )
    assert main(["--config", cfg]) == 1  # not 3: the pipeline failure wins
    failed = [e for e in events(capsys) if e["event"] == "run.failed"][0]
    assert failed["reason"] == "VideoOpenError" and failed["reports_failed"] >= 1


def test_pipeline_failed_reporting_ok_sends_failed_event(api, tmp_path):  # noqa: F811
    cfg = write_config(
        tmp_path,
        video_path=str(tmp_path / "no_such_dir" / "feed.mp4"),
        reporting=reporting(api.url),
    )
    assert main(["--config", cfg]) == 1
    kinds = [body["event"] for _, body in api.received]
    assert kinds == ["started", "failed"]
    assert "VideoOpenError" in api.received[-1][1]["detail"]
