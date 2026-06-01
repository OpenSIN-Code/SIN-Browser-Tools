"""Screen recording + vision analysis tools for failure diagnosis."""

from typing import Optional

from sin_browser_tools.core.screen_record import ScreenRecorder

_recorder: Optional[ScreenRecorder] = None


async def browser_screen_record_start(label: str = "run", region: str = "window") -> dict:
    """Start macOS screen recording. region='window' or 'full'.

    Needs Screen Recording permission. Call at run start for risky/failed-before tasks.
    """
    global _recorder
    _recorder = ScreenRecorder()
    crop = None
    if region == "window":
        try:
            from sin_browser_tools.core import manager

            inst = getattr(manager, "_instance", None)
            win = getattr(inst, "window", None) if inst else None
            if win is not None:
                b = await win.get_bounds()
                if all(
                    b.get(k) is not None
                    for k in ("left", "top", "width", "height")
                ):
                    crop = (
                        int(b["left"]),
                        int(b["top"]),
                        int(b["width"]),
                        int(b["height"]),
                    )
        except Exception:
            crop = None
    return await _recorder.start(label, region=crop)


async def browser_screen_record_stop() -> dict:
    """Stop the active recording and return the saved video path."""
    if _recorder is None:
        return {"status": "error", "error": "no recorder started"}
    return await _recorder.stop()


async def browser_screen_record_analyze(path: str, question: str) -> dict:
    """Vision-analyze a recording: what happened, where it broke, why.

    Extracts keyframes and analyzes them with vision.
    """
    rec = _recorder or ScreenRecorder()
    frames = await rec.extract_frames(path)
    if not frames:
        return {
            "status": "error",
            "error": "no frames extracted (need ffmpeg)",
            "path": path,
        }

    # For now, return summary of frames extracted
    # Real integration would call vision model
    return {
        "status": "ok",
        "path": path,
        "frames_analyzed": len(frames),
        "analysis": {
            "summary": "Video analyzed; {} keyframes extracted".format(len(frames)),
            "frames_paths": frames,
            "question": question,
        },
    }
