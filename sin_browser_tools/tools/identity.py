"""Per-session identity -- User-Agent, locale, timezone, geolocation.

Replaces the previously hardcoded macOS UA / de-DE / Europe-Berlin defaults with
configurable values. UA/locale/timezone are read by the manager when it builds a
context, so they take effect on the *next* context (re)build. Geolocation is
applied live to the current context.
"""

from __future__ import annotations

from typing import Optional

from sin_browser_tools.core import manager
from sin_browser_tools.core.result import ok, err


# Coherent presets -- the UA matches the declared platform/locale so the
# fingerprint is internally consistent (a Linux UA on a Linux host, etc.).
_PRESETS = {
    "linux_desktop": {
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "locale": "en-US",
        "timezone_id": "UTC",
    },
    "windows_desktop": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "locale": "en-US",
        "timezone_id": "UTC",
    },
    "macos_desktop": {
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "locale": "en-US",
        "timezone_id": "UTC",
    },
    "android_mobile": {
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
        ),
        "locale": "en-US",
        "timezone_id": "UTC",
    },
}


async def browser_set_identity(
    preset: Optional[str] = None,
    user_agent: Optional[str] = None,
    locale: Optional[str] = None,
    timezone_id: Optional[str] = None,
    geolocation: Optional[dict] = None,
) -> dict:
    """Set identity parameters for the browser session.

    ``preset`` is one of ``linux_desktop``, ``windows_desktop``,
    ``macos_desktop``, ``android_mobile``; individual fields override the preset.
    ``geolocation`` is ``{"latitude": .., "longitude": ..}`` and is applied to
    the current context immediately. UA/locale/timezone are stored on the
    manager and take effect on the next context (re)build.
    """
    cfg = dict(_PRESETS.get(preset, {})) if preset else {}
    if preset and not cfg:
        return err(
            f"Unknown preset: {preset}",
            status="bad_args",
            available_presets=sorted(_PRESETS),
        )
    if user_agent:
        cfg["user_agent"] = user_agent
    if locale:
        cfg["locale"] = locale
    if timezone_id:
        cfg["timezone_id"] = timezone_id

    if not cfg and not geolocation:
        return err(
            "Provide a preset, at least one identity field, or geolocation",
            status="bad_args",
            available_presets=sorted(_PRESETS),
        )

    # Stored on the manager; new_context() reads these (see manager defaults).
    if cfg.get("user_agent"):
        manager.user_agent = cfg["user_agent"]
    if cfg.get("locale"):
        manager.locale = cfg["locale"]
    if cfg.get("timezone_id"):
        manager.timezone_id = cfg["timezone_id"]

    geo_applied = False
    if geolocation:
        try:
            await manager.context.set_geolocation(geolocation)
            await manager.context.grant_permissions(["geolocation"])
            geo_applied = True
        except Exception as e:
            return err(f"geolocation failed: {e}", status="error")

    return ok(
        status="identity_set",
        applied=cfg,
        geolocation_applied=geo_applied,
        note=(
            "UA/locale/timezone take effect on the next context rebuild; "
            "geolocation is live."
        ),
    )
