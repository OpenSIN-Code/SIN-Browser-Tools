"""macOS Spaces ("Schreibtische") steuern: Browser-Fenster auf einen anderen
Space verschieben, Spaces auflisten/erstellen. Austauschbare Backends mit
Auto-Erkennung (hammerspoon > yabai > applescript).

Auf Nicht-macOS-Systemen liefern alle Operationen eine strukturierte
"unsupported"-Antwort statt einer Exception.
"""

import asyncio
import json
import platform
import shutil
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

IS_MACOS = platform.system() == "Darwin"


async def _run(cmd: list[str], timeout: float = 8.0) -> tuple[int, str, str]:
    """Subprozess ausführen -> (returncode, stdout, stderr)."""
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
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


class SpaceBackend:
    name = "base"

    @classmethod
    def available(cls) -> bool:
        return False

    async def list_spaces(self) -> list[dict]:
        raise NotImplementedError

    async def create_space(self) -> dict:
        raise NotImplementedError

    async def move_window(self, pid: int, title: Optional[str], space_index: int) -> dict:
        raise NotImplementedError

    async def window_space(self, pid: int, title: Optional[str]) -> dict:
        raise NotImplementedError


# --------------------------------------------------------------------------- yabai
class YabaiBackend(SpaceBackend):
    name = "yabai"

    @classmethod
    def available(cls) -> bool:
        return IS_MACOS and shutil.which("yabai") is not None

    async def list_spaces(self) -> list[dict]:
        rc, out, _ = await _run(["yabai", "-m", "query", "--spaces"])
        if rc != 0:
            return []
        try:
            spaces = json.loads(out)
        except json.JSONDecodeError:
            return []
        return [
            {"index": s.get("index"), "label": s.get("label", ""),
             "display": s.get("display"), "is_visible": s.get("is-visible", False)}
            for s in spaces
        ]

    async def create_space(self) -> dict:
        rc, _, err = await _run(["yabai", "-m", "space", "--create"])
        if rc != 0:
            return {"status": "error", "error": err.strip() or "create failed"}
        spaces = await self.list_spaces()
        return {"status": "ok", "space_index": spaces[-1]["index"] if spaces else None}

    async def _find_window_id(self, pid: int, title: Optional[str]) -> Optional[int]:
        rc, out, _ = await _run(["yabai", "-m", "query", "--windows"])
        if rc != 0:
            return None
        try:
            windows = json.loads(out)
        except json.JSONDecodeError:
            return None
        # 1) exakte PID-Übereinstimmung; 2) Titel-Substring als Fallback.
        for w in windows:
            if pid and w.get("pid") == pid:
                return w.get("id")
        if title:
            for w in windows:
                if title.lower() in (w.get("title", "").lower()):
                    return w.get("id")
        # 3) erstes Chromium/Chrome-Fenster.
        for w in windows:
            if w.get("app", "").lower() in ("chromium", "google chrome", "chrome"):
                return w.get("id")
        return None

    async def move_window(self, pid: int, title: Optional[str], space_index: int) -> dict:
        win_id = await self._find_window_id(pid, title)
        if win_id is None:
            return {"status": "error", "error": "browser window not found in yabai query"}
        rc, _, err = await _run(["yabai", "-m", "window", str(win_id), "--space", str(space_index)])
        if rc != 0:
            return {"status": "error", "error": err.strip() or "move failed",
                    "hint": "yabai window-move needs the scripting addition; see docs/PERMISSIONS_MACOS.md"}
        return {"status": "ok", "backend": self.name, "window_id": win_id, "space_index": space_index}

    async def window_space(self, pid: int, title: Optional[str]) -> dict:
        rc, out, _ = await _run(["yabai", "-m", "query", "--windows"])
        if rc != 0:
            return {"status": "error", "error": "yabai query failed"}
        try:
            windows = json.loads(out)
        except json.JSONDecodeError:
            return {"status": "error", "error": "bad yabai output"}
        for w in windows:
            if pid and w.get("pid") == pid:
                return {"status": "ok", "space_index": w.get("space")}
        return {"status": "error", "error": "window not found"}


# --------------------------------------------------------------- Hammerspoon hs.spaces
class HammerspoonBackend(SpaceBackend):
    name = "hammerspoon"

    @classmethod
    def available(cls) -> bool:
        return IS_MACOS and shutil.which("hs") is not None

    async def _hs(self, lua: str) -> tuple[int, str, str]:
        return await _run(["hs", "-c", lua])

    async def list_spaces(self) -> list[dict]:
        # hs.spaces.allSpaces() -> {screenUUID = {spaceID, ...}}; wir flatten zu Indexliste.
        lua = (
            "local s=hs.spaces.allSpaces();local out={};local i=0;"
            "for _,ids in pairs(s) do for _,id in ipairs(ids) do i=i+1;"
            "out[#out+1]=string.format('%d:%d', i, id) end end;"
            "return table.concat(out, ',')"
        )
        rc, out, _ = await self._hs(lua)
        if rc != 0 or not out.strip():
            return []
        spaces = []
        for chunk in out.strip().split(","):
            if ":" in chunk:
                idx, sid = chunk.split(":", 1)
                spaces.append({"index": int(idx), "space_id": int(sid)})
        return spaces

    async def create_space(self) -> dict:
        # hs.spaces.addSpaceToScreen() legt einen Space auf dem Hauptscreen an.
        lua = (
            "local scr=hs.screen.mainScreen():getUUID();"
            "local ok=hs.spaces.addSpaceToScreen(scr);return tostring(ok)"
        )
        rc, out, err = await self._hs(lua)
        if rc != 0:
            return {"status": "error", "error": err.strip() or "create failed"}
        spaces = await self.list_spaces()
        return {"status": "ok", "space_index": spaces[-1]["index"] if spaces else None}

    async def _window_id(self, pid: int, title: Optional[str]) -> Optional[str]:
        # Hammerspoon adressiert Fenster über hs.window:id() (CGWindowID).
        if pid:
            lua = (
                "local app=hs.application.applicationForPID({pid});"
                "if not app then return '' end;"
                "local w=app:mainWindow();"
                "if not w then local ws=app:allWindows(); w=ws[1] end;"
                "if not w then return '' end;return tostring(w:id())"
            ).format(pid=pid)
            rc, out, _ = await self._hs(lua)
            if rc == 0 and out.strip().isdigit():
                return out.strip()
        if title:
            lua = (
                "local w=hs.window.find([[{title}]]);"
                "if not w then return '' end;return tostring(w:id())"
            ).format(title=title.replace("]]", ""))
            rc, out, _ = await self._hs(lua)
            if rc == 0 and out.strip().isdigit():
                return out.strip()
        return None

    async def move_window(self, pid: int, title: Optional[str], space_index: int) -> dict:
        win_id = await self._window_id(pid, title)
        if not win_id:
            return {"status": "error", "error": "browser window not found via Hammerspoon"}
        # space_index (1-basiert) -> echte spaceID auflösen.
        spaces = await self.list_spaces()
        match = next((s for s in spaces if s["index"] == space_index), None)
        if not match:
            return {"status": "error", "error": "space index {} out of range".format(space_index)}
        lua = "return tostring(hs.spaces.moveWindowToSpace({wid}, {sid}))".format(
            wid=win_id, sid=match["space_id"]
        )
        rc, out, err = await self._hs(lua)
        if rc != 0 or "true" not in out.lower():
            return {"status": "error", "error": (err or out).strip() or "move failed",
                    "hint": "Hammerspoon needs Accessibility permission; see docs/PERMISSIONS_MACOS.md"}
        return {"status": "ok", "backend": self.name, "window_id": win_id,
                "space_index": space_index, "space_id": match["space_id"]}

    async def window_space(self, pid: int, title: Optional[str]) -> dict:
        win_id = await self._window_id(pid, title)
        if not win_id:
            return {"status": "error", "error": "window not found"}
        lua = "return tostring(hs.spaces.windowSpaces({wid})[1])".format(wid=win_id)
        rc, out, _ = await self._hs(lua)
        if rc != 0 or not out.strip().isdigit():
            return {"status": "error", "error": "could not resolve space"}
        sid = int(out.strip())
        spaces = await self.list_spaces()
        idx = next((s["index"] for s in spaces if s["space_id"] == sid), None)
        return {"status": "ok", "space_id": sid, "space_index": idx}


# --------------------------------------------------------------- AppleScript fallback
class AppleScriptBackend(SpaceBackend):
    name = "applescript"

    @classmethod
    def available(cls) -> bool:
        return IS_MACOS and shutil.which("osascript") is not None

    async def list_spaces(self) -> list[dict]:
        return []  # AppleScript kann Spaces nicht zuverlässig auflisten

    async def create_space(self) -> dict:
        return {"status": "unsupported",
                "error": "AppleScript cannot create Spaces. Install yabai or Hammerspoon.",
                "see": "docs/PERMISSIONS_MACOS.md"}

    async def move_window(self, pid, title, space_index) -> dict:
        return {"status": "unsupported",
                "error": "Moving a window to another Space requires yabai or Hammerspoon (hs.spaces).",
                "see": "docs/PERMISSIONS_MACOS.md"}

    async def window_space(self, pid, title) -> dict:
        return {"status": "unsupported", "error": "not available via AppleScript"}


def detect_backend(preferred: str = "auto") -> Optional[SpaceBackend]:
    """Wählt das beste verfügbare Backend (oder ein explizit gewünschtes)."""
    registry = {
        "yabai": YabaiBackend,
        "hammerspoon": HammerspoonBackend,
        "applescript": AppleScriptBackend,
    }
    if preferred != "auto":
        cls = registry.get(preferred)
        if cls and cls.available():
            return cls()
        return None
    # Sicherer Default: Hammerspoon zuerst (nur Accessibility-Permission, KEIN
    # SIP-Teil-Deaktivieren), dann yabai, dann AppleScript-Fallback.
    for cls in (HammerspoonBackend, YabaiBackend, AppleScriptBackend):
        if cls.available():
            return cls()
    return None


class SpaceController:
    """Hoch-Level-Fassade über das aktive Backend, vom Tool-Layer genutzt."""

    def __init__(self, browser_pid: Optional[int], window_title_hint: Optional[str],
                 preferred: str = "auto"):
        self.browser_pid = browser_pid
        self.window_title_hint = window_title_hint
        self.backend = detect_backend(preferred)

    def _no_backend(self) -> dict:
        if not IS_MACOS:
            return {"status": "unsupported", "error": "Spaces are macOS-only.",
                    "platform": platform.system()}
        return {"status": "error",
                "error": "No Spaces backend available. Install yabai or Hammerspoon.",
                "see": "docs/PERMISSIONS_MACOS.md"}

    async def list_spaces(self) -> dict:
        if not self.backend:
            return self._no_backend()
        return {"status": "ok", "backend": self.backend.name,
                "spaces": await self.backend.list_spaces()}

    async def create_space(self) -> dict:
        if not self.backend:
            return self._no_backend()
        return await self.backend.create_space()

    async def move_to_space(self, space_index: int) -> dict:
        if not self.backend:
            return self._no_backend()
        return await self.backend.move_window(self.browser_pid, self.window_title_hint, space_index)

    async def current_space(self) -> dict:
        if not self.backend:
            return self._no_backend()
        return await self.backend.window_space(self.browser_pid, self.window_title_hint)

    async def send_to_background_space(self, create_if_needed: bool = True) -> dict:
        """Convenience: dediziertes Hintergrund-Space finden/erstellen und Fenster
        dorthin legen, ohne den aktiven Space des Nutzers zu wechseln."""
        if not self.backend:
            return self._no_backend()
        spaces = await self.backend.list_spaces()
        # Ziel = letzter, NICHT sichtbarer Space; sonst neuen erstellen.
        target = None
        for s in spaces:
            if not s.get("is_visible", False):
                target = s["index"]
        if target is None and create_if_needed:
            created = await self.backend.create_space()
            if created.get("status") != "ok":
                return created
            target = created.get("space_index")
        if target is None:
            return {"status": "error", "error": "no background space available"}
        result = await self.backend.move_window(self.browser_pid, self.window_title_hint, target)
        result["background_space_index"] = target
        return result
