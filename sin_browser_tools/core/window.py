"""Fenster-Steuerung über das Chrome DevTools Protocol (CDP).

Plattformübergreifend (macOS/Windows/Linux), solange der Browser HEADFUL läuft.
Headless-Shell besitzt kein OS-Fenster -> die Methoden liefern dann einen
strukturierten Hinweis statt einer Exception.

Vordefinierte Modi:
    small      1024 x 720
    medium     1280 x 800
    large      1600 x 1000
    maximized  (windowState=maximized)
    fullscreen (windowState=fullscreen)
    custom     -> explizite (width, height)
"""

from typing import Optional

import structlog
from playwright.async_api import BrowserContext, Page

logger = structlog.get_logger(__name__)

# Vordefinierte Pixel-Größen (Breite, Höhe) für die "Fenstergröße"-Modi.
WINDOW_PRESETS: dict[str, tuple[int, int]] = {
    "small": (1024, 720),
    "medium": (1280, 800),
    "large": (1600, 1000),
}
WINDOW_STATES = {"normal", "minimized", "maximized", "fullscreen"}


def window_mode_to_args(
    mode: str,
    size: Optional[tuple[int, int]] = None,
    position: Optional[tuple[int, int]] = None,
) -> list[str]:
    """Erzeugt Chromium-CLI-Flags für die INITIALE Fenstergeometrie beim Launch.

    Wird von BrowserManager.start_local() in launch_args["args"] gemerged.
    """
    args: list[str] = []
    mode = (mode or "default").lower()

    if mode == "fullscreen":
        args.append("--start-fullscreen")
        return args
    if mode == "maximized":
        args.append("--start-maximized")
        return args

    w, h = None, None
    if mode in WINDOW_PRESETS:
        w, h = WINDOW_PRESETS[mode]
    elif size:
        w, h = size
    if w and h:
        args.append("--window-size={},{}".format(int(w), int(h)))
    if position:
        args.append("--window-position={},{}".format(int(position[0]), int(position[1])))
    return args


class WindowController:
    """Laufzeit-Steuerung des Browser-Fensters via CDP Browser.*-Domain."""

    def __init__(
        self,
        context: BrowserContext,
        page: Page,
        browser_pid: Optional[int] = None,
    ):
        self._context = context
        self._page = page
        self.browser_pid = browser_pid

    def set_page(self, page: Page) -> None:
        """Aktive Page (= Ziel-Tab/Fenster) wechseln, z.B. nach Tab-Switch."""
        self._page = page

    async def _window_for_target(self):
        """(cdp_session, windowId, bounds) für die aktive Page holen.

        Browser.* ist eine Browser-globale Domain; eine page-gebundene
        CDP-Session genügt aber, um getWindowForTarget aufzulösen.
        """
        cdp = await self._context.new_cdp_session(self._page)
        info = await cdp.send("Browser.getWindowForTarget")
        return cdp, info["windowId"], info.get("bounds", {})

    async def get_bounds(self) -> dict:
        """Aktuelle Fenster-Bounds + windowState lesen."""
        cdp, window_id, bounds = await self._window_for_target()
        try:
            return {
                "window_id": window_id,
                "left": bounds.get("left"),
                "top": bounds.get("top"),
                "width": bounds.get("width"),
                "height": bounds.get("height"),
                "window_state": bounds.get("windowState", "normal"),
            }
        finally:
            await _safe_detach(cdp)

    async def _set_bounds(self, window_id, cdp, **bounds) -> None:
        await cdp.send(
            "Browser.setWindowBounds", {"windowId": window_id, "bounds": bounds}
        )

    async def set_state(self, state: str) -> dict:
        """windowState setzen: normal | minimized | maximized | fullscreen."""
        state = state.lower()
        if state not in WINDOW_STATES:
            return {"status": "error", "error": "state must be one of {}".format(sorted(WINDOW_STATES))}
        cdp, window_id, _ = await self._window_for_target()
        try:
            # Chromium verlangt: aus maximized/fullscreen erst nach normal,
            # bevor ein anderer Nicht-Normal-State gesetzt wird.
            if state in ("maximized", "fullscreen"):
                try:
                    await self._set_bounds(window_id, cdp, windowState="normal")
                except Exception:
                    pass
            await self._set_bounds(window_id, cdp, windowState=state)
            return {"status": "ok", "window_state": state}
        except Exception as e:
            return _headful_hint(e)
        finally:
            await _safe_detach(cdp)

    async def set_bounds(
        self,
        left: Optional[int] = None,
        top: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> dict:
        """Position/Größe in Pixeln setzen (immer im windowState=normal)."""
        cdp, window_id, _ = await self._window_for_target()
        try:
            # Resize/Move geht nur im normal-State.
            try:
                await self._set_bounds(window_id, cdp, windowState="normal")
            except Exception:
                pass
            bounds = {}
            if left is not None:
                bounds["left"] = int(left)
            if top is not None:
                bounds["top"] = int(top)
            if width is not None:
                bounds["width"] = int(width)
            if height is not None:
                bounds["height"] = int(height)
            if not bounds:
                return {"status": "error", "error": "no bounds given"}
            await self._set_bounds(window_id, cdp, **bounds)
            return {"status": "ok", **bounds}
        except Exception as e:
            return _headful_hint(e)
        finally:
            await _safe_detach(cdp)

    async def set_mode(
        self, mode: str, size: Optional[tuple[int, int]] = None
    ) -> dict:
        """High-Level: small|medium|large|maximized|fullscreen|custom."""
        mode = (mode or "").lower()
        if mode in ("maximized", "fullscreen"):
            return await self.set_state(mode)
        if mode in WINDOW_PRESETS:
            w, h = WINDOW_PRESETS[mode]
            return await self.set_bounds(width=w, height=h)
        if mode in ("custom", "normal") and size:
            return await self.set_bounds(width=size[0], height=size[1])
        return {
            "status": "error",
            "error": "unknown mode {!r}; use small|medium|large|maximized|fullscreen|custom".format(mode),
        }


async def _safe_detach(cdp) -> None:
    try:
        await cdp.detach()
    except Exception:
        pass


def _headful_hint(err: Exception) -> dict:
    return {
        "status": "error",
        "error": str(err),
        "hint": (
            "Window control needs a real OS window (headful). Start the manager "
            "with headless=False (or SIN_HEADLESS=false). Headless-shell has no window."
        ),
    }
