"""Validated pipeline configuration.

The models here replace the prototype's raw dict. Every field is typed and
range-checked, unknown keys are rejected, and nothing falls back to a default
silently. load_config() is the only way in, and it either returns a fully
valid PipelineConfig or raises ConfigError with a message that says what is
wrong and where.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from engine.errors import ConfigError


class _Strict(BaseModel):
    """Base for all config sections: unknown keys are an error, not ignored."""

    model_config = ConfigDict(extra="forbid")


class DetectorConfig(_Strict):
    type: Literal["hsv_mask"]
    sport: str = Field(min_length=1)
    min_area: int = Field(gt=0, description="Smallest contour area (px^2) accepted as a boundary")
    max_coverage: float = Field(
        gt=0.0, le=1.0, description="Largest share of the frame a boundary may cover and still count as a pitch"
    )


class CropConfig(_Strict):
    aspect_ratio: str = Field(pattern=r"^\d+:\d+$")
    padding_px: int = Field(ge=0)


class SamplingConfig(_Strict):
    analysis_fps: float = Field(gt=0, description="How many frames per second of video to inspect")
    max_frames: int | None = Field(gt=0, description="Stop after this many inspected frames; null for no cap")
    downscale: int = Field(ge=1, description="Shrink frames by this factor before detection; 1 keeps full size")


class LoggingConfig(_Strict):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    format: Literal["json", "text"]
    progress_every: int = Field(gt=0, description="Emit a progress record every N inspected frames")


class ResilienceConfig(_Strict):
    max_consecutive_frame_errors: int = Field(
        gt=0, description="Stop the run when this many inspected frames in a row fail to decode or detect"
    )


class PipelineConfig(_Strict):
    video_path: str = Field(min_length=1)
    output_path: str | None = Field(min_length=1, description="Write the run summary as JSON here; null to skip")
    confidence_threshold: float = Field(ge=0.0, le=1.0)
    sampling: SamplingConfig
    field_detector: DetectorConfig
    crop_search: CropConfig
    logging: LoggingConfig
    resilience: ResilienceConfig


def load_config(path: str | Path) -> PipelineConfig:
    """Read a YAML file and return a validated PipelineConfig.

    Raises ConfigError if the file is missing, is not valid YAML, is not a
    mapping, or fails validation. The message lists every problem found.
    """
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"config file {path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"config file {path} must contain a mapping at the top level")

    try:
        return PipelineConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(path, exc)) from exc


def _format_validation_error(path: Path, exc: ValidationError) -> str:
    lines = [f"config file {path} is invalid:"]
    for err in exc.errors():
        location = ".".join(str(part) for part in err["loc"]) or "<root>"
        lines.append(f"  - {location}: {err['msg']}")
    return "\n".join(lines)
