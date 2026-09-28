"""Exception types raised by the engine.

Two families, two exit codes:

- ConfigError, exit 2: the run never started. Fix the config and rerun.
- PipelineError, exit 1: the run started and could not finish. The log says why.

Per-frame problems (no boundary, a bad mask, one failed decode) are not
exceptions at all. They are counted, logged, and skipped. They only become a
PipelineError when they repeat enough in a row to mean the stream itself is
broken.
"""


class ConfigError(Exception):
    """Configuration is missing, unparsable, or invalid. Raised before any work starts."""


class PipelineError(Exception):
    """The run cannot continue. Base class for fatal runtime failures."""


class VideoOpenError(PipelineError):
    """The video source could not be opened at all."""


class VideoProbeError(PipelineError):
    """The video source opened but reports no usable stream properties."""


class StreamBrokenError(PipelineError):
    """Too many consecutive frames failed; the stream is treated as broken rather than noisy."""
