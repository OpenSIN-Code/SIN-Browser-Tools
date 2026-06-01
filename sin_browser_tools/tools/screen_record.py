"""Screen recording + vision analysis tools for failure diagnosis."""

import base64
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


async def browser_screen_record_analyze(
    path: str, question: str, max_frames: int = 8, include_images: bool = True
) -> dict:
    """Vision-analyze a recording: extract ordered keyframes for the agent to inspect.

    This tool does NOT call a separate VLM. It extracts keyframes from the video
    and returns them as ordered, timestamped Base64 PNGs so the calling (vision-
    capable) agent model can look at them directly and answer `question` -- the
    same pattern as browser_vision. The agent should report the frame where the
    UI diverged, any visual blockers (cookie banner, modal, CAPTCHA, spinner,
    error toast), unexpected redirects, and a concrete browser_* fix.
    """
    rec = _recorder or ScreenRecorder()
    frames = await rec.extract_frames(path, max_frames=max_frames)
    if not frames:
        return {
            "status": "error",
            "error": "no frames extracted (ffmpeg required, or video missing)",
            "path": path,
        }

    frame_payload = []
    for idx, fp in enumerate(frames):
        entry = {"index": idx, "path": fp, "approx_second": idx}
        if include_images:
            try:
                with open(fp, "rb") as fh:
                    entry["base64"] = base64.b64encode(fh.read()).decode("utf-8")
                    entry["format"] = "png"
            except OSError as e:
                entry["error"] = "could not read frame: {}".format(e)
        frame_payload.append(entry)

    return {
        "status": "ok",
        "path": path,
        "frames_analyzed": len(frames),
        "question": question,
        "instructions": (
            "Inspect the ordered keyframes (≈1s apart). Identify the frame index "
            "where the UI diverged from the intended action, name any visual "
            "blocker, note unexpected redirects, and recommend ONE concrete "
            "browser_* fix."
        ),
        "frames": frame_payload,
    }
