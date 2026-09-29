"""HTTP client for the reporting service.

The client takes validated models and serialises them itself. It reports
failures to reach the service through the log and a counter; it does not
raise into the pipeline. Whether such a failure changes the run's exit code
is the entry point's decision.
"""

import logging
from typing import Protocol

import requests

from engine.reporting.models import JobEvent, ProgressReport

log = logging.getLogger("engine.reporting")


class Reporter(Protocol):
    job_id: str
    run_id: str
    failures: int

    def progress(self, report: ProgressReport) -> None: ...

    def event(self, event: JobEvent) -> None: ...


class NullReporter:
    """Used when reporting is disabled. Builds nothing, sends nothing, never fails."""

    def __init__(self, job_id: str, run_id: str):
        self.job_id = job_id
        self.run_id = run_id
        self.failures = 0

    def progress(self, report: ProgressReport) -> None:
        pass

    def event(self, event: JobEvent) -> None:
        pass


class HttpReporter:
    PROGRESS_PATH = "/api/v1/jobs/progress"
    EVENTS_PATH = "/api/v1/jobs/events"

    def __init__(self, base_url: str, job_id: str, run_id: str, timeout_s: float):
        self.base_url = base_url.rstrip("/")
        self.job_id = job_id
        self.run_id = run_id
        self.timeout_s = timeout_s
        self.failures = 0
        self.sent = 0
        self._session = requests.Session()

    def progress(self, report: ProgressReport) -> None:
        self._post(self.PROGRESS_PATH, report)

    def event(self, event: JobEvent) -> None:
        self._post(self.EVENTS_PATH, event)

    def _post(self, path: str, payload: ProgressReport | JobEvent) -> None:
        url = self.base_url + path
        body = payload.model_dump(mode="json")
        try:
            response = self._session.post(url, json=body, timeout=self.timeout_s)
            response.raise_for_status()
        except requests.RequestException as exc:
            self.failures += 1
            log.warning(
                "reporting.failed",
                extra={"url": url, "payload": type(payload).__name__, "error": str(exc), "failures": self.failures},
            )
            return
        self.sent += 1
        log.debug("reporting.sent", extra={"url": url, "payload": type(payload).__name__})
