"""HTTP client for the reporting service.

The client takes validated models and serialises them itself. It never raises
into the pipeline: a request that fails after its retries is counted and
logged, and the run goes on. Whether that changes the exit code is the entry
point's decision, made after the video work is done.

Two protections keep a dead service from hurting the run:
- bounded retries with a short backoff, so a blip is absorbed;
- after N failed requests in a row the client stops sending progress, so the
  pipeline is not paying a timeout per report. Lifecycle events (started,
  completed, failed) are always attempted, because the outcome is what the
  orchestrator most needs to hear.
"""

import logging
import time
from typing import Protocol

import requests

from engine.reporting.models import JobEvent, ProgressReport

log = logging.getLogger("engine.reporting")


class Reporter(Protocol):
    job_id: str
    run_id: str
    sent: int
    failures: int
    degraded: bool

    def progress(self, report: ProgressReport) -> None: ...

    def event(self, event: JobEvent) -> None: ...


class NullReporter:
    """Used when reporting is disabled. Builds nothing, sends nothing, never fails."""

    def __init__(self, job_id: str, run_id: str):
        self.job_id = job_id
        self.run_id = run_id
        self.sent = 0
        self.failures = 0
        self.degraded = False

    def progress(self, report: ProgressReport) -> None:
        pass

    def event(self, event: JobEvent) -> None:
        pass


class HttpReporter:
    PROGRESS_PATH = "/api/v1/jobs/progress"
    EVENTS_PATH = "/api/v1/jobs/events"

    def __init__(
        self,
        base_url: str,
        job_id: str,
        run_id: str,
        timeout_s: float,
        max_retries: int = 0,
        retry_backoff_s: float = 0.0,
        max_consecutive_failures: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.job_id = job_id
        self.run_id = run_id
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s
        self.max_consecutive_failures = max_consecutive_failures
        self.sent = 0
        self.failures = 0  # requests that failed after all their attempts
        self.skipped = 0  # progress reports not sent because the client had degraded
        self.degraded = False
        self._consecutive_failures = 0
        self._session = requests.Session()

    def progress(self, report: ProgressReport) -> None:
        if self.degraded:
            self.skipped += 1
            return
        self._post(self.PROGRESS_PATH, report)

    def event(self, event: JobEvent) -> None:
        self._post(self.EVENTS_PATH, event)

    def _post(self, path: str, payload: ProgressReport | JobEvent) -> None:
        url = self.base_url + path
        body = payload.model_dump(mode="json")
        attempts = self.max_retries + 1
        last_error = ""

        for attempt in range(1, attempts + 1):
            try:
                response = self._session.post(url, json=body, timeout=self.timeout_s)
                response.raise_for_status()
            except requests.RequestException as exc:
                last_error = str(exc)
                if attempt < attempts:
                    log.debug("reporting.retry", extra={"url": url, "attempt": attempt, "error": last_error})
                    time.sleep(self.retry_backoff_s * attempt)
            else:
                self.sent += 1
                self._consecutive_failures = 0
                log.debug("reporting.sent", extra={"url": url, "payload": type(payload).__name__})
                return

        self.failures += 1
        self._consecutive_failures += 1
        log.warning(
            "reporting.failed",
            extra={
                "url": url,
                "payload": type(payload).__name__,
                "attempts": attempts,
                "error": last_error,
                "failures": self.failures,
            },
        )
        if not self.degraded and self._consecutive_failures >= self.max_consecutive_failures:
            self.degraded = True
            log.warning(
                "reporting.degraded",
                extra={
                    "consecutive_failures": self._consecutive_failures,
                    "detail": "progress reports suspended for the rest of the run; lifecycle events still attempted",
                },
            )
