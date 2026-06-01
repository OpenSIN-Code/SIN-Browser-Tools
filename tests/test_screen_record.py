"""Tests for screen recording."""

import pytest
import platform

from sin_browser_tools.core.screen_record import ScreenRecorder


def test_screen_recorder_unsupported_non_macos():
    """Non-macOS returns unsupported response."""
    if platform.system() == "Darwin":
        pytest.skip("Test is for non-macOS only")
    
    rec = ScreenRecorder()
    result = rec._unsupported()
    assert result["status"] == "unsupported"
    assert result["platform"] != "Darwin"


@pytest.mark.asyncio
@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS-only")
async def test_screen_recorder_no_backend_returns_error():
    """If ffmpeg/screencapture unavailable, returns error (not exception)."""
    rec = ScreenRecorder()
    if not rec._backend:
        result = await rec.start("test")
        assert result["status"] in ("error", "unsupported")


@pytest.mark.asyncio
@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS-only")
async def test_screen_recorder_stop_without_start():
    """stop() with no active recording returns error."""
    rec = ScreenRecorder()
    result = await rec.stop()
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_learning_tools_screen_record_api():
    """screen_record_start/stop tools are callable."""
    from sin_browser_tools.tools import screen_record
    
    result = await screen_record.browser_screen_record_stop()
    # Should error since we never started
    assert result["status"] == "error"
