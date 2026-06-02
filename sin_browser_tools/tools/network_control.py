"""Request interception -- block resources for speed, or mock responses for
deterministic runs.

Blocking images/media/fonts/css makes pages load faster and more stably when
the agent only needs the DOM. Mocking lets a flow be tested against a fixed
backend response instead of a flaky live one.
"""

from __future__ import annotations

import re
from typing import Optional

from sin_browser_tools.core import manager
from sin_browser_tools.core.result import ok, err


_DEFAULT_BLOCK_TYPES = {"image", "media", "font", "stylesheet"}


async def browser_block_resources(
    resource_types: Optional[list[str]] = None,
    url_patterns: Optional[list[str]] = None,
) -> dict:
    """Abort matching requests.

    ``resource_types`` defaults to image/media/font/stylesheet. ``url_patterns``
    are regexes matched against the request URL. Installs a route on the active
    page; call ``browser_unroute_all`` to remove it.
    """
    page = manager.page
    types = set(resource_types) if resource_types else set(_DEFAULT_BLOCK_TYPES)
    try:
        patterns = [re.compile(p) for p in (url_patterns or [])]
    except re.error as e:
        return err(f"Invalid url_pattern regex: {e}", status="bad_args")

    async def _route(route):
        req = route.request
        if req.resource_type in types or any(p.search(req.url) for p in patterns):
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", _route)
    return ok(
        status="routing",
        blocking_types=sorted(types),
        blocking_patterns=url_patterns or [],
    )


async def browser_mock_response(
    url_pattern: str,
    body: str,
    status: int = 200,
    content_type: str = "application/json",
) -> dict:
    """Intercept ``url_pattern`` (regex) and return a fixed response.

    Useful for deterministic tests: pin an API response so the flow always sees
    the same data. Non-matching requests pass through untouched.
    """
    page = manager.page
    try:
        rx = re.compile(url_pattern)
    except re.error as e:
        return err(f"Invalid url_pattern regex: {e}", status="bad_args")

    async def _route(route):
        if rx.search(route.request.url):
            await route.fulfill(
                status=status, content_type=content_type, body=body
            )
        else:
            await route.continue_()

    await page.route("**/*", _route)
    return ok(status="routing", mocking=url_pattern, response_status=status)


async def browser_unroute_all() -> dict:
    """Remove all active routes (block/mock) from the page."""
    await manager.page.unroute("**/*")
    return ok(status="cleared")
