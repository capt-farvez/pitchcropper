"""Metrics come from valid detections only; every inspected frame lands in exactly one bucket."""

import json

from shapely.geometry import Polygon

from engine.aggregate import DetectionAggregator, RejectReason, RunSummary


def box(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def make():
    return DetectionAggregator(frame_width=100, frame_height=100, max_coverage=0.9)


def test_every_frame_is_counted_once():
    agg = make()
    agg.consider(0, box(10, 10, 60, 60))
    agg.consider(1, None)
    agg.reject(RejectReason.DECODE_FAILED)
    agg.consider(3, box(0, 0, 100, 100))  # whole frame, over max_coverage
    agg.consider(4, Polygon([(0, 0), (10, 10), (10, 0), (0, 10)]))  # bow-tie, invalid

    s = agg.summary(frame_count=5)
    assert s.inspected == 5
    assert s.valid == 1
    assert s.rejected[RejectReason.NO_BOUNDARY] == 1
    assert s.rejected[RejectReason.DECODE_FAILED] == 1
    assert s.rejected[RejectReason.TOO_LARGE] == 1
    assert s.rejected[RejectReason.INVALID_GEOMETRY] == 1
    assert s.inspected == s.valid + sum(s.rejected.values())


def test_invalid_frames_do_not_move_the_metrics():
    agg = make()
    agg.consider(0, box(0, 0, 50, 50))  # 2500
    agg.consider(1, box(0, 0, 100, 100))  # rejected, would be 10000
    agg.consider(2, None)
    s = agg.summary(frame_count=3)
    assert s.area_px == {"min": 2500, "median": 2500, "mean": 2500, "max": 2500}
    assert s.coverage["median"] == 0.2


def test_representative_boundary_is_the_median_area_polygon():
    agg = make()
    agg.consider(0, box(0, 0, 10, 10))  # 100
    agg.consider(1, box(0, 0, 50, 50))  # 2500  <- median
    agg.consider(2, box(0, 0, 80, 80))  # 6400
    s = agg.summary(frame_count=3)
    assert s.boundary_frame_index == 1
    assert sorted(map(tuple, s.boundary)) == [(0, 0), (0, 50), (50, 0), (50, 50)]


def test_no_valid_detections_gives_null_metrics_not_zeros():
    agg = make()
    agg.consider(0, None)
    s = agg.summary(frame_count=1)
    assert s.valid == 0
    assert s.area_px is None and s.coverage is None and s.boundary is None


def test_summary_round_trips_through_json():
    agg = make()
    agg.consider(0, box(10, 10, 60, 60))
    s = agg.summary(frame_count=1)
    again = RunSummary.model_validate(json.loads(s.model_dump_json()))
    assert again == s
