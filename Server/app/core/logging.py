"""Application logging.

Uses the standard library only. Log lines include a timestamp, level,
logger name and message. Request bodies are never logged because they
may later contain candidate evidence.
"""

import logging

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(level: str) -> None:
    """Configure process-wide logging from the application environment."""
    numeric_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format=_LOG_FORMAT,
        datefmt=_LOG_DATE_FORMAT,
        force=True,
    )
    logging.captureWarnings(True)
