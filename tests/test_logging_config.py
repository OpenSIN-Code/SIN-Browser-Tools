"""Regression tests for logging_config.

Issue #41: importing sin_browser_tools must NOT wipe the host application's
root-logger handlers. We simulate the SINator-fireworksai pattern:

    1. host calls logging.basicConfig with custom stdout + file handlers
    2. host imports sin_browser_tools
    3. host's handlers must still be attached and still receive log records
"""

import io
import logging
import sys

import pytest

import sin_browser_tools  # noqa: F401  — side-effect: ensure_configured()
from sin_browser_tools.core import logging_config


@pytest.fixture(autouse=True)
def _reset_logging_state():
    """Snapshot the root logger before each test, restore after."""
    saved_handlers = list(logging.root.handlers)
    saved_level = logging.root.level
    saved_disabled = logging.root.disabled
    saved_configured = logging_config._configured
    yield
    logging.root.handlers = saved_handlers
    logging.root.setLevel(saved_level)
    logging.root.disabled = saved_disabled
    logging_config._configured = saved_configured


def test_ensure_configured_does_not_clobber_existing_handlers():
    """Issue #41: when root logger already has handlers, ensure_configured
    must not replace them."""
    host_stream = io.StringIO()
    host_file = io.StringIO()
    host_handler_1 = logging.StreamHandler(host_stream)
    host_handler_2 = logging.StreamHandler(host_file)
    logging.basicConfig(
        level=logging.INFO,
        format="HOST-FMT %(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[host_handler_1, host_handler_2],
        force=True,
    )
    assert len(logging.root.handlers) == 2

    # Simulate import-time call from __init__.py
    logging_config._configured = False
    logging_config.ensure_configured()

    # Handlers must still be there, in the same order, with the same formatters.
    assert len(logging.root.handlers) == 2
    assert logging.root.handlers[0] is host_handler_1
    assert logging.root.handlers[1] is host_handler_2
    assert host_handler_1.formatter is not None
    assert "%(asctime)s" in host_handler_1.formatter._fmt


def test_ensure_configured_routes_through_host_handlers():
    """structlog log records must end up in the host's file handler."""
    host_stream = io.StringIO()
    host_handler = logging.StreamHandler(host_stream)
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[host_handler],
        force=True,
    )

    logging_config._configured = False
    logging_config.ensure_configured()

    logger = logging_config.structlog.get_logger("test.host")
    logger.info("hello_from_structlog", key="value")

    output = host_stream.getvalue()
    assert "hello_from_structlog" in output, (
        f"structlog record did not reach host handler. Got: {output!r}"
    )
    assert "key" in output or "value" in output, (
        f"structlog KV arg did not propagate. Got: {output!r}"
    )


def test_configure_logging_still_replaces_when_called_explicitly():
    """Explicit configure_logging() must keep its 'clean slate' semantics."""
    host_stream = io.StringIO()
    host_handler = logging.StreamHandler(host_stream)
    logging.basicConfig(
        level=logging.INFO,
        format="HOST-FMT %(message)s",
        handlers=[host_handler],
        force=True,
    )

    # Explicit call → should replace the host handler
    logging_config.configure_logging(level="INFO")

    assert host_handler not in logging.root.handlers, (
        "configure_logging() must replace existing handlers when called explicitly"
    )
    assert len(logging.root.handlers) >= 1


def test_ensure_configured_idempotent():
    """Second call must be a no-op."""
    host_stream = io.StringIO()
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.StreamHandler(host_stream)],
        force=True,
    )
    handlers_before = list(logging.root.handlers)

    logging_config._configured = False
    logging_config.ensure_configured()
    logging_config.ensure_configured()  # second call

    assert logging.root.handlers == handlers_before


def test_no_handlers_falls_back_to_full_setup():
    """If root has no handlers, ensure_configured must install a default."""
    logging.root.handlers = []
    assert not logging.root.handlers

    logging_config._configured = False
    logging_config.ensure_configured()

    assert len(logging.root.handlers) >= 1, (
        "ensure_configured() must install a default handler when none exist"
    )
    assert logging_config.is_configured()


def test_is_configured_export():
    """is_configured is part of the public API (used in __all__)."""
    assert hasattr(sin_browser_tools, "is_configured")
    assert callable(sin_browser_tools.is_configured)
