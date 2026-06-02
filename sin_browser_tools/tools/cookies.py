"""Cookie write tools -- set and clear cookies.

Reading cookies already exists elsewhere; what was missing is the ability to
*inject* auth/session cookies (e.g. to restore a logged-in state) and to clear
them for a clean slate. Both operate on the active browser context.
"""

from __future__ import annotations

from sin_browser_tools.core import manager
from sin_browser_tools.core.result import ok, err


async def browser_cookies_set(cookies: list[dict]) -> dict:
    """Add cookies to the active context.

    Each cookie dict needs ``name`` + ``value`` and EITHER ``url`` OR
    ``domain`` + ``path``. Example::

        [{"name": "sid", "value": "abc",
          "domain": ".example.com", "path": "/"}]
    """
    if not cookies:
        return err("No cookies provided", status="bad_args")

    for i, c in enumerate(cookies):
        if "name" not in c or "value" not in c:
            return err(
                f"Cookie #{i} needs both 'name' and 'value'",
                status="bad_args",
            )
        if "url" not in c and not ("domain" in c and "path" in c):
            return err(
                f"Cookie #{i} needs 'url' OR both 'domain' and 'path'",
                status="bad_args",
            )

    await manager.context.add_cookies(cookies)
    return ok(status="set", count=len(cookies))


async def browser_cookies_clear() -> dict:
    """Remove all cookies from the active context."""
    await manager.context.clear_cookies()
    return ok(status="cleared")
