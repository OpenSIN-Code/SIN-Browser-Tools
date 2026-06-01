"""Fenster- und macOS-Space-Tools.

Fenster (plattformübergreifend, HEADFUL):
    browser_get_window_bounds, browser_set_window_bounds, browser_set_window_mode,
    browser_maximize_window, browser_minimize_window, browser_fullscreen_window,
    browser_restore_window, browser_move_window

macOS Spaces (Schreibtische):
    browser_list_spaces, browser_create_space, browser_move_to_space,
    browser_get_window_space, browser_send_to_background_space
"""

from typing import Optional

from sin_browser_tools.core import manager
from sin_browser_tools.core.spaces import SpaceController


def _window():
    """Aktiven WindowController holen; klare Fehlermeldung, falls nicht headful/gestartet."""
    inst = getattr(manager, "_instance", None) or manager._require()
    win = getattr(inst, "window", None)
    if win is None:
        raise RuntimeError(
            "No window controller. Start the browser headful first: "
            "await manager.start_local(headless=False) (or SIN_HEADLESS=false)."
        )
    # Stets auf die aktuell aktive Page zeigen (nach Tab-Wechseln).
    try:
        win.set_page(inst._page)
    except Exception:
        pass
    return win


async def _title_hint() -> Optional[str]:
    try:
        return await manager.page.title()
    except Exception:
        return None


def _space_controller(title: Optional[str]) -> SpaceController:
    from sin_browser_tools.opensin_config import get_config
    inst = getattr(manager, "_instance", None)
    pid = getattr(inst, "_browser_pid", None)
    return SpaceController(pid, title, preferred=get_config().space_backend)


# --- Fenster -----------------------------------------------------------------

async def browser_get_window_bounds() -> dict:
    """Aktuelle Fensterposition/-größe + windowState lesen (headful)."""
    return await _window().get_bounds()


async def browser_set_window_bounds(
    left: int = None, top: int = None, width: int = None, height: int = None
) -> dict:
    """Fenster auf exakte Pixel setzen. Beliebige Teilmenge der vier Werte."""
    return await _window().set_bounds(left=left, top=top, width=width, height=height)


async def browser_set_window_mode(mode: str = "medium") -> dict:
    """Fenstergröße per Preset: small | medium | large | maximized | fullscreen | custom.

    small=1024x720, medium=1280x800, large=1600x1000. 'custom' braucht vorher
    browser_set_window_bounds. Funktioniert nur headful (echtes OS-Fenster).
    """
    return await _window().set_mode(mode)


async def browser_maximize_window() -> dict:
    """Fenster maximieren (windowState=maximized)."""
    return await _window().set_state("maximized")


async def browser_minimize_window() -> dict:
    """Fenster minimieren (in den Dock/Taskleiste)."""
    return await _window().set_state("minimized")


async def browser_fullscreen_window() -> dict:
    """Echtes Vollbild (windowState=fullscreen)."""
    return await _window().set_state("fullscreen")


async def browser_restore_window() -> dict:
    """Fenster auf Normalzustand zurücksetzen (aus max/min/fullscreen)."""
    return await _window().set_state("normal")


async def browser_move_window(left: int, top: int) -> dict:
    """Fenster an Bildschirmposition (left, top) verschieben (Pixel)."""
    return await _window().set_bounds(left=left, top=top)


# --- macOS Spaces ------------------------------------------------------------

async def browser_list_spaces() -> dict:
    """Alle macOS-Spaces (Schreibtische) auflisten. macOS-only."""
    return await _space_controller(await _title_hint()).list_spaces()


async def browser_create_space() -> dict:
    """Einen neuen macOS-Space (Schreibtisch) anlegen. Braucht yabai/Hammerspoon."""
    return await _space_controller(await _title_hint()).create_space()


async def browser_move_to_space(space_index: int) -> dict:
    """Browser-Fenster auf den Space mit `space_index` (1-basiert) verschieben.

    Der Nutzer-Schreibtisch wechselt dabei NICHT -> das Fenster verschwindet vom
    aktuellen Space und liegt auf einem anderen (für den Nutzer 'im Hintergrund',
    real ein Vordergrund-Fenster auf einem anderen Schreibtisch). macOS-only.
    """
    return await _space_controller(await _title_hint()).move_to_space(space_index)


async def browser_get_window_space() -> dict:
    """Auf welchem Space liegt das Browser-Fenster aktuell? macOS-only."""
    return await _space_controller(await _title_hint()).current_space()


async def browser_send_to_background_space(create_if_needed: bool = True) -> dict:
    """Fenster auf einen dedizierten Hintergrund-Space legen (anlegen, falls keiner
    frei ist), ohne den aktiven Schreibtisch des Nutzers zu wechseln. macOS-only.
    """
    return await _space_controller(await _title_hint()).send_to_background_space(create_if_needed)
