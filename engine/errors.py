"""Exception types raised by the engine."""


class ConfigError(Exception):
    """Configuration is missing, unparsable, or invalid. Raised before any work starts."""
