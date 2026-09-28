"""The one seam that flexes: how a frame becomes a field mask.

Everything downstream (polygon derivation, metrics, aggregation, reporting) is
the same for every sport and deployment. What changes is the detector. A
detector takes a BGR frame and returns a binary mask where non-zero pixels are
"playing field", or None when it could not produce one.
"""

from typing import Protocol

import numpy as np


class FieldDetector(Protocol):
    name: str

    def detect(self, frame: np.ndarray) -> np.ndarray | None:
        """Return a uint8 mask (0 or 255) the same height and width as the frame, or None."""
        ...
