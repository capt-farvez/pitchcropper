"""Mask to polygon conversion and the downscale round trip."""

import numpy as np

from engine.geometry import polygon_from_mask, upscale


def rect_mask(h, w, top, left, bottom, right):
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[top:bottom, left:right] = 255
    return mask


def test_polygon_from_rectangle_mask_has_expected_area():
    poly = polygon_from_mask(rect_mask(100, 100, 10, 10, 60, 90), min_area=10)
    assert poly is not None
    # contour follows pixel centres, so the area is one pixel short on each axis
    assert poly.area == (60 - 10 - 1) * (90 - 10 - 1)


def test_polygon_below_min_area_is_rejected():
    assert polygon_from_mask(rect_mask(100, 100, 10, 10, 15, 15), min_area=1000) is None


def test_empty_mask_gives_no_polygon():
    assert polygon_from_mask(np.zeros((50, 50), dtype=np.uint8), min_area=1) is None


def test_upscale_maps_back_to_full_resolution():
    poly = polygon_from_mask(rect_mask(100, 100, 10, 10, 60, 90), min_area=10)
    full = upscale(poly, 2)
    assert full.bounds == tuple(v * 2 for v in poly.bounds)
    assert upscale(poly, 1) is poly
