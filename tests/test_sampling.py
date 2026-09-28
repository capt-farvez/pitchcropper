"""Work must follow the number of frames inspected, not the length of the video."""

import cv2
import pytest

from engine.geometry import frame_bounds
from engine.sampling import compute_stride, iter_sampled_frames, probe_video


@pytest.mark.parametrize(
    "source_fps, analysis_fps, expected",
    [(30, 30, 1), (30, 2, 15), (30, 1, 30), (25, 2, 12), (30, 60, 1), (29.97, 2, 15)],
)
def test_compute_stride(source_fps, analysis_fps, expected):
    assert compute_stride(source_fps, analysis_fps) == expected


def test_probe_reads_stream_properties_once(make_video):
    cap = cv2.VideoCapture(make_video(30))
    info = probe_video(cap)
    cap.release()
    assert info.fps == pytest.approx(30)
    assert info.frame_count == 30
    assert (info.width, info.height) == (1280, 720)


def test_sampled_indexes_follow_stride(make_video):
    cap = cv2.VideoCapture(make_video(60))
    indexes = [i for i, _ in iter_sampled_frames(cap, stride=15)]
    cap.release()
    assert indexes == [0, 15, 30, 45]


def test_max_frames_caps_inspection_regardless_of_length(make_video):
    short = cv2.VideoCapture(make_video(60))
    long = cv2.VideoCapture(make_video(120))
    n_short = sum(1 for _ in iter_sampled_frames(short, stride=1, max_frames=10))
    n_long = sum(1 for _ in iter_sampled_frames(long, stride=1, max_frames=10))
    short.release()
    long.release()
    assert n_short == n_long == 10


def test_stride_divides_work_not_just_output(make_video):
    cap = cv2.VideoCapture(make_video(120))
    inspected = sum(1 for _ in iter_sampled_frames(cap, stride=15))
    cap.release()
    assert inspected == 8  # 120 frames / 15, not 120


def test_frame_bounds_is_computed_once_per_size():
    a = frame_bounds(1280, 720)
    b = frame_bounds(1280, 720)
    c = frame_bounds(1920, 1080)
    assert a is b
    assert a is not c
    assert a.area == 1280 * 720
