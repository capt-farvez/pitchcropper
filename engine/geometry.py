"""Turn a field mask into a boundary polygon and measure it.

Anything that depends only on the frame size is computed once and cached:
the prototype rebuilt the frame-bounds polygon for every frame.
"""

from functools import lru_cache

import cv2
import numpy as np
from shapely.geometry import Polygon
from shapely.affinity import scale as scale_polygon


@lru_cache(maxsize=8)
def frame_bounds(width: int, height: int) -> Polygon:
    """Polygon covering the whole frame. Cached per size, since it never changes within a run."""
    return Polygon([(0, 0), (width, 0), (width, height), (0, height)])


def polygon_from_mask(mask: np.ndarray, min_area: float) -> Polygon | None:
    """Largest external contour of the mask as a polygon, or None if there is none large enough."""
    try:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) > min_area:
                pts = largest.reshape(-1, 2)
                if len(pts) >= 3:
                    return Polygon(pts)
    except Exception:
        pass
    return None


def upscale(poly: Polygon, factor: int) -> Polygon:
    """Map a polygon found on a downscaled frame back to full-resolution pixel coordinates."""
    if factor == 1:
        return poly
    return scale_polygon(poly, xfact=factor, yfact=factor, origin=(0, 0))
