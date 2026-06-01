"""macOS screen recording + frame extraction for vision analysis.

Backends: ffmpeg (avfoundation) > screencapture. Auto-detection.
Non-macOS returns structured "unsupported" response.
"""

import asyncio
import platform
import shutil
import time
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)
IS_MACOS = platform.system() == "Darwin"


async def _run(cmd: list[str], timeout: float = 30.0) -> tuple[int, str, str]:
    """Run a subprocess command -> (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "", "timeout"
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


class ScreenRecorder:
    """One recording session: start() -> ... -> stop() returns video path."""

    def __init__(self, out_dir: str = ".sin_recordings"):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(exist_ok=True)
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._path: Optional[Path] = None
        self._backend = self._detect_backend()

    def _detect_backend(self) -> Optional[str]:
        if not IS_MACOS:
            return None
        if shutil.which("ffmpeg"):
            return "ffmpeg"
        if shutil.which("screencapture"):
            return "screencapture"
        return None

    def _unsupported(self) -> dict:
        if not IS_MACOS:
            return {
                "status": "unsupported",
                "error": "Screen recording is macOS-only.",
                "platform": platform.system(),
            }
        return {
            "status": "error",
            "error": "No recorder backend (install ffmpeg: brew install ffmpeg).",
            "see": "docs/PERMISSIONS_MACOS.md",
        }

    async def start(
        self,
        label: str = "run",
        region: Optional[tuple[int, int, int, int]] = None,
    ) -> dict:
        """Start recording. region=(x,y,w,h) for window-confined capture."""
        if not self._backend:
            return self._unsupported()
        ts = time.strftime("%Y%m%d-%H%M%S")
        self._path = self.out_dir / "{}-{}.mp4".format(label.replace("/", "_"), ts)

        if self._backend == "ffmpeg":
            cmd = ["ffmpeg", "-y", "-f", "avfoundation", "-r", "5", "-i", "1:none"]
            if region:
                x, y, w, h = region
                cmd += ["-vf", "crop={}:{}:{}:{}".format(w, h, x, y)]
            cmd += ["-pix_fmt", "yuv420p", str(self._path)]
        else:
            cmd = ["screencapture", "-v", str(self._path)]

        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info("screen recording started", backend=self._backend, label=label)
        return {
            "status": "ok",
            "backend": self._backend,
            "path": str(self._path),
            "recording": True,
            "label": label,
        }

    async def stop(self) -> dict:
        """Stop recording cleanly."""
        if not self._proc:
            return {"status": "error", "error": "no active recording"}
        try:
            if self._backend == "ffmpeg":
                try:
                    self._proc.stdin.write(b"q\n")
                    await self._proc.stdin.drain()
                except Exception:
                    self._proc.terminate()
            else:
                self._proc.terminate()
            await asyncio.wait_for(self._proc.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            self._proc.kill()
        finally:
            self._proc = None

        exists = self._path and self._path.exists()
        logger.info("screen recording stopped", path=str(self._path) if self._path else None, exists=exists)
        return {
            "status": "ok" if exists else "error",
            "path": str(self._path) if self._path else None,
            "exists": bool(exists),
        }

    async def extract_frames(
        self,
        video_path: str,
        every_s: float = 1.0,
        max_frames: int = 12,
    ) -> list[str]:
        """Extract keyframes via ffmpeg -> list of PNG paths."""
        if not shutil.which("ffmpeg"):
            logger.debug("ffmpeg not found, cannot extract frames")
            return []
        frames_dir = Path(video_path).with_suffix("")
        frames_dir.mkdir(exist_ok=True)
        pattern = str(frames_dir / "frame-%03d.png")
        rc, _, _ = await _run(
            [
                "ffmpeg", "-y", "-i", video_path,
                "-vf", "fps=1/{}".format(every_s),
                "-frames:v", str(max_frames),
                pattern,
            ],
            timeout=60.0,
        )
        if rc != 0:
            logger.warning("frame extraction failed", video_path=video_path)
            return []
        frames = sorted(str(p) for p in frames_dir.glob("frame-*.png"))
        logger.info("frames extracted", count=len(frames), video_path=video_path)
        return frames
