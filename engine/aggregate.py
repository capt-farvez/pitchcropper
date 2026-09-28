"""Turn per-frame outcomes into one result.

Every inspected frame ends up in exactly one bucket: a valid detection, or a
rejection with a reason. Metrics are computed over valid detections only, so
a close-up, a camera cut or a bad decode can never move the numbers. The
rejection counts are part of the output too; an operator should see how much
of the feed was unusable, not just what was found.
"""

from enum import Enum
from statistics import mean, median

import numpy as np
from pydantic import Field
from shapely.geometry import Polygon

from engine.models import StrictModel


class RejectReason(str, Enum):
    DECODE_FAILED = "decode_failed"  # grabbed but could not be decoded
    DETECT_FAILED = "detect_failed"  # detector raised
    NO_BOUNDARY = "no_boundary"  # no mask, no contour, or contour below min_area
    INVALID_GEOMETRY = "invalid_geometry"  # self-intersecting or degenerate polygon
    TOO_LARGE = "too_large"  # covers more of the frame than a pitch plausibly can


class RunSummary(StrictModel):
    """The final output of a run. Also the shape reported to the platform."""

    frame_count: int = Field(ge=0, description="Frames in the source")
    inspected: int = Field(ge=0, description="Frames actually analysed")
    valid: int = Field(ge=0)
    rejected: dict[RejectReason, int]
    area_px: dict[str, float] | None = Field(description="min, median, mean, max over valid boundaries; null if none")
    coverage: dict[str, float] | None = Field(description="Boundary area over frame area, same statistics")
    boundary: list[list[float]] | None = Field(description="Representative boundary: the valid polygon of median area")
    boundary_frame_index: int | None


class DetectionAggregator:
    def __init__(self, frame_width: int, frame_height: int, max_coverage: float):
        self.frame_area = float(frame_width * frame_height)
        self.max_coverage = max_coverage
        self.inspected = 0
        self.rejected: dict[RejectReason, int] = {r: 0 for r in RejectReason}
        self._areas: list[float] = []
        self._coverages: list[float] = []
        self._polygons: list[tuple[int, Polygon]] = []

    def reject(self, reason: RejectReason) -> None:
        self.inspected += 1
        self.rejected[reason] += 1

    def consider(self, frame_index: int, poly: Polygon | None) -> RejectReason | None:
        """Classify a derived polygon. Returns the rejection reason, or None if it was accepted."""
        self.inspected += 1
        if poly is None:
            reason = RejectReason.NO_BOUNDARY
        elif not poly.is_valid or poly.area <= 0:
            reason = RejectReason.INVALID_GEOMETRY
        elif poly.area / self.frame_area > self.max_coverage:
            reason = RejectReason.TOO_LARGE
        else:
            self._areas.append(poly.area)
            self._coverages.append(poly.area / self.frame_area)
            self._polygons.append((frame_index, poly))
            return None
        self.rejected[reason] += 1
        return reason

    @property
    def valid(self) -> int:
        return len(self._areas)

    def summary(self, frame_count: int) -> RunSummary:
        if not self._areas:
            return RunSummary(
                frame_count=frame_count,
                inspected=self.inspected,
                valid=0,
                rejected=dict(self.rejected),
                area_px=None,
                coverage=None,
                boundary=None,
                boundary_frame_index=None,
            )

        med = median(self._areas)
        rep_index, rep_poly = min(self._polygons, key=lambda item: abs(item[1].area - med))
        coords = np.asarray(rep_poly.simplify(1.0).exterior.coords[:-1], dtype=float)

        return RunSummary(
            frame_count=frame_count,
            inspected=self.inspected,
            valid=len(self._areas),
            rejected=dict(self.rejected),
            area_px=_stats(self._areas),
            coverage=_stats(self._coverages),
            boundary=coords.round(1).tolist(),
            boundary_frame_index=rep_index,
        )


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "min": round(min(values), 1),
        "median": round(median(values), 1),
        "mean": round(mean(values), 1),
        "max": round(max(values), 1),
    }
