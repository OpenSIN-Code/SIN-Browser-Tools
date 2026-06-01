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


@pytest.mark.asyncio
async def test_analyze_missing_video_returns_error():
    """analyze on a non-existent video returns a clean error (no exception)."""
    from sin_browser_tools.tools import screen_record

    result = await screen_record.browser_screen_record_analyze(
        "/nonexistent/video.mp4", "what happened?"
    )
    assert result["status"] == "error"
    assert "frames" not in result or not result.get("frames")


@pytest.mark.asyncio
async def test_analyze_returns_base64_frames(tmp_path, monkeypatch):
    """analyze returns ordered Base64 PNG frames for the agent to inspect."""
    from sin_browser_tools.tools import screen_record
    from sin_browser_tools.core import screen_record as core_sr

    # Fake-Frames erzeugen
    f1 = tmp_path / "frame-001.png"
    f2 = tmp_path / "frame-002.png"
    f1.write_bytes(b"\x89PNG\r\n\x1a\n_fake1")
    f2.write_bytes(b"\x89PNG\r\n\x1a\n_fake2")

    async def fake_extract(self, video_path, every_s=1.0, max_frames=12):
        return [str(f1), str(f2)]

    monkeypatch.setattr(core_sr.ScreenRecorder, "extract_frames", fake_extract)

    result = await screen_record.browser_screen_record_analyze(
        str(tmp_path / "vid.mp4"), "diagnose"
    )
    assert result["status"] == "ok"
    assert result["frames_analyzed"] == 2
    assert result["frames"][0]["index"] == 0
    assert result["frames"][0]["format"] == "png"
    assert "base64" in result["frames"][0]


class TestAutoRecordHook:
    """Manager failure-counter + auto-record hook (B-feature wiring)."""

    def test_success_resets_counter(self):
        from sin_browser_tools.core.manager import BrowserManager

        mgr = BrowserManager()
        mgr._consecutive_failures = 3
        mgr.note_tool_success()
        assert mgr._consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_failure_increments_counter(self, monkeypatch):
        from sin_browser_tools.core.manager import BrowserManager

        mgr = BrowserManager()
        mgr.auto_record_on_failure = False  # nicht wirklich aufnehmen
        await mgr.note_tool_failure("browser_click", "boom")
        assert mgr._consecutive_failures == 1
        await mgr.note_tool_failure("browser_click", "boom")
        assert mgr._consecutive_failures == 2
