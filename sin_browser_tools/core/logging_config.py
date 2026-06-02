"""Centralized structlog configuration.

BUGFIX #29: structlog.get_logger() without prior configure() returns a BoundLogger
that formats KV args via repr(), producing logs like:
    2024-01-15 ... 'emails'=5 'phones'=2
instead of proper JSON/KeyValue output for Loki/Datadog ingestion.

This module provides configure_logging() which MUST be called once at startup
(e.g. in __init__.py or entry points) to enable proper structured logging.
"""

import logging
import sys
from typing import Optional

import structlog


def configure_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Optional[str] = None,
) -> None:
    """Configure structlog for proper structured logging output.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        json_format: If True, output JSON lines (for Loki/Datadog). If False,
            use colored console output for local dev.
        log_file: Optional file path to write logs to.

    Call this ONCE at application startup before any get_logger() calls.
    """
    # Standard library logging config (structlog wraps stdlib)
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers = []
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    handlers.append(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=handlers,
        force=True,  # Override any existing config
    )

    # Shared processors for all output formats
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        # JSON Lines for production/log aggregation
        renderer = structlog.processors.JSONRenderer()
    else:
        # Colored console output for local development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure the formatter for stdlib handlers
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    for handler in logging.root.handlers:
        handler.setFormatter(formatter)


# Auto-configure with sensible defaults on import if not already configured.
# This ensures that even if the user forgets to call configure_logging(),
# logs will still be properly formatted (not repr'd KV args).
_configured = False


def ensure_configured() -> None:
    """Ensure logging is configured at least once with defaults."""
    global _configured
    if not _configured:
        configure_logging()
        _configured = True
