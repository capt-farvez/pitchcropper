"""Detector registry. Adding a detector means one class and one line here."""

from collections.abc import Callable

from engine.config import DetectorConfig
from engine.detectors.base import FieldDetector
from engine.detectors.hsv_mask import HsvMaskDetector
from engine.errors import ConfigError

_REGISTRY: dict[str, Callable[[DetectorConfig], FieldDetector]] = {
    "hsv_mask": HsvMaskDetector,
}


def build_detector(config: DetectorConfig) -> FieldDetector:
    try:
        factory = _REGISTRY[config.type]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY))
        raise ConfigError(f"unknown field_detector.type '{config.type}' (known: {known})") from None
    return factory(config)


__all__ = ["FieldDetector", "HsvMaskDetector", "build_detector"]
