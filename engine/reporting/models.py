"""What goes over the wire, and nothing else.

Both payloads derive from the same StrictModel as the config. A field that is
not declared here cannot be sent, and a value out of range cannot be built.
The reporting client accepts these models only, never a dict.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field

from engine.aggregate import RunSummary
from engine.models import StrictModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProgressReport(StrictModel):
    """POST /api/v1/jobs/progress. Sent every `logging.progress_every` inspected frames."""

    job_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=utc_now)
    frame_index: int = Field(ge=0)
    inspected: int = Field(ge=0)
    expected_inspected: int = Field(ge=0)
    percent: float | None = Field(ge=0, le=100)
    valid: int = Field(ge=0)
    rejected: int = Field(ge=0)


class JobEvent(StrictModel):
    """POST /api/v1/jobs/events. One at start, one at the end, whichever way it ends."""

    job_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=utc_now)
    event: Literal["started", "completed", "failed"]
    detail: str | None = None
    summary: RunSummary | None = None
