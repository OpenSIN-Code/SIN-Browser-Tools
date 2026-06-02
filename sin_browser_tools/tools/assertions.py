"""Assertion tools -- make the *verify* step of the snapshot/act/verify loop
deterministic.

An agent that only *acts* and never *verifies* is guessing. These tools turn a
verification into an explicit, machine-checkable result: each call confirms
exactly ONE condition and returns ``ok=True/False`` so the agent can branch on
fact, not assumption.
"""

from __future__ import annotations

from typing import Optional

from sin_browser_tools.core import manager
from sin_browser_tools.core.result import ok, err


async def browser_assert(
    text: Optional[str] = None,
    selector: Optional[str] = None,
    url_contains: Optional[str] = None,
    timeout_ms: int = 5000,
) -> dict:
    """Confirm exactly one condition about the current page.

    Provide exactly ONE of:
    - ``text``: a visible text substring must exist in ``document.body``
    - ``selector``: a CSS selector must be present and visible
    - ``url_contains``: the current URL must contain the substring

    Returns ``ok=True`` with the observed value on success, or ``ok=False`` with
    ``status="assert_failed"`` on failure -- never raises.
    """
    page = manager.page

    if url_contains is not None:
        actual = page.url
        if url_contains in actual:
            return ok(status="asserted", check="url_contains", actual_url=actual)
        return err(
            f"URL does not contain {url_contains!r}",
            status="assert_failed",
            check="url_contains",
            actual_url=actual,
        )

    if selector is not None:
        try:
            await page.wait_for_selector(
                selector, state="visible", timeout=timeout_ms
            )
            return ok(status="asserted", check="selector", selector=selector)
        except Exception:
            return err(
                f"Selector not visible within {timeout_ms}ms: {selector}",
                status="assert_failed",
                check="selector",
                selector=selector,
            )

    if text is not None:
        try:
            await page.wait_for_function(
                "t => document.body && document.body.innerText.includes(t)",
                arg=text,
                timeout=timeout_ms,
            )
            return ok(status="asserted", check="text", text=text)
        except Exception:
            return err(
                f"Text not found within {timeout_ms}ms: {text!r}",
                status="assert_failed",
                check="text",
                text=text,
            )

    return err(
        "Provide exactly one of: text, selector, url_contains",
        status="bad_args",
    )
