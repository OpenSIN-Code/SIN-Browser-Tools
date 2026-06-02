"""Centralized structlog configuration.

BUGFIX #29: structlog.get_logger() without prior configure() returns a BoundLogger
that formats KV args via repr(), producing logs like:
    2024-01-15 ... 'emails'=5 'phones'=2
instead of proper JSON/KeyValue output for Loki/Datadog ingestion.

BUGFIX #41: The previous implementation called ``logging.basicConfig(force=True)``
unconditionally from ``ensure_configured()`` (auto-invoked on package import), which
wiped the root-logger handlers of any downstream application that had already
configured logging (e.g. ``SINator-fireworksai/agent_toolbox/start_toolbox.py``
loses its ``toolbox.log`` FileHandler). The fix splits the two concerns:

- :func:`configure_logging` — explicit opt-in. Replaces root handlers and sets up
  full structlog→stdlib routing. Intended for apps that want a clean slate.
- :func:`ensure_configured` — implicit, called once from ``__init__.py``. Detects
  whether the host app has already configured logging; if so, configures structlog
  only (via stdlib ``LoggerFactory``, so records flow through the host's existing
  handlers); if not, delegates to :func:`configure_logging` for sensible defaults.
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
    """Full structlog + stdlib setup. **Replaces any existing root handlers.**

    Intended for apps that want a clean slate — typically called once from a
    top-level entry point (e.g. ``mcp_server.main()``). Apps that already
    configured their own logging should *not* call this; use
    :func:`ensure_configured` instead (or do nothing — it runs at import time).

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        json_format: If True, output JSON lines (for Loki/Datadog). If False,
            use colored console output for local dev.
        log_file: Optional file path to write logs to.
    """
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
        force=True,
    )

    _configure_structlog(json_format=json_format)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_shared_processors(),
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            _renderer(json_format=json_format),
        ],
    )

    for handler in logging.root.handlers:
        handler.setFormatter(formatter)

    _mark_configured()


def _shared_processors() -> list:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]


def _renderer(json_format: bool):
    if json_format:
        return structlog.processors.JSONRenderer()
    return structlog.dev.ConsoleRenderer(colors=True)


def _configure_structlog(json_format: bool = False) -> None:
    """Wire structlog to stdlib without touching root handlers.

    structlog records flow through the existing root handlers; if those handlers
    have a ProcessorFormatter the output is pretty, otherwise it's a best-effort
    repr. Either way, the host's handlers and formatters are left intact.
    """
    structlog.configure(
        processors=_shared_processors()
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


_configured = False


def _mark_configured() -> None:
    global _configured
    _configured = True


def is_configured() -> bool:
    """True after the first :func:`ensure_configured` or :func:`configure_logging` call."""
    return _configured


def ensure_configured() -> None:
    """Idempotent minimal setup. Respects the host application's existing logging.

    Behaviour:
    - If the root logger has **no** handlers → behaves like :func:`configure_logging`
      (sets up stdlib stderr handler + structlog).
    - If the root logger **already** has handlers → only configures structlog's
      processors. The host's stdlib handlers and formatters are left untouched,
      so ``toolbox.log`` / proxy logs / etc. keep working.

    Called automatically from ``sin_browser_tools/__init__.py`` at import time.
    Safe to call multiple times — only the first call has any effect.
    """
    global _configured
    if _configured:
        return

    if logging.root.handlers:
        # Host app has its own logging. Don't touch it.
        _configure_structlog(json_format=_should_use_json())
    else:
        # No host setup — apply sensible defaults.
        configure_logging()

    _configured = True


def _should_use_json() -> bool:
    """JSON output if explicitly requested via env, else auto-detect TTY."""
    import os

    if os.environ.get("SIN_BROWSER_LOG_JSON") == "1":
        return True
    if os.environ.get("SIN_BROWSER_LOG_JSON") == "0":
        return False
    return not sys.stderr.isatty()
