"""
Network Interception Tool -- Faengt API-Responses ab.
Die robustere Alternative zu DOM-Parsing bei modernen SPAs.

Schluessel-Erkenntnis: Moderne Web-Apps (GMX, Salesforce, Office365) laden
ihre Daten via XHR/Fetch. Wir fangen den JSON-Response ab statt den DOM zu parsen.
Das ist 100x robuster und unabhaengig von Shadow DOM, OOPIF und SPA-Rendering-Timing.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from playwright.async_api import Page, Response
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class InterceptedResponse:
    """Abgefangene HTTP Response."""

    url: str
    status: int
    method: str
    headers: dict
    body: Any = None
    timestamp: float = field(default_factory=time.time)


class NetworkInterceptor:
    """
    Faengt HTTP-Responses nach URL-Pattern ab und speichert sie.
    Ermoeglicht strukturierte Daten-Extraktion ohne DOM-Parsing.
    """

    def __init__(self, page: Page):
        self.page = page
        self._intercepted: list[InterceptedResponse] = []
        self._patterns: list[tuple[str, bool]] = []  # (pattern, capture_body)
        self._installed = False

    def add_pattern(self, pattern: str, capture_body: bool = True):
        """
        Fuegt ein URL-Pattern hinzu (Substring-Match).
        Example: '/api/v3/messages', 'listMessages'
        """
        self._patterns.append((pattern, capture_body))

    async def start(self):
        """Aktiviert den Network-Listener."""
        if self._installed:
            return
        self.page.on("response", self._handle_response)
        self._installed = True
        logger.debug("Network interception started", patterns=len(self._patterns))

    async def stop(self):
        """Deaktiviert den Listener."""
        if not self._installed:
            return
        try:
            self.page.remove_listener("response", self._handle_response)
        except Exception:
            pass
        self._installed = False

    async def _handle_response(self, response: Response):
        """Handler fuer alle Responses."""
        url = response.url

        for pattern, capture_body in self._patterns:
            if pattern in url:
                intercepted = InterceptedResponse(
                    url=url,
                    status=response.status,
                    method=response.request.method,
                    headers=dict(response.headers),
                )

                if capture_body:
                    try:
                        content_type = response.headers.get("content-type", "")
                        if "json" in content_type:
                            intercepted.body = await response.json()
                        elif "text" in content_type:
                            intercepted.body = await response.text()
                    except Exception as e:
                        logger.debug("Body capture failed", url=url, error=str(e))

                self._intercepted.append(intercepted)
                logger.debug("Intercepted response", url=url[:80], status=response.status)
                break

    def get_intercepted(
        self, pattern: Optional[str] = None
    ) -> list[InterceptedResponse]:
        """Gibt abgefangene Responses zurueck, optional gefiltert."""
        if pattern is None:
            return list(self._intercepted)
        return [r for r in self._intercepted if pattern in r.url]

    def clear(self):
        """Leert den Buffer."""
        self._intercepted.clear()

    async def wait_for_pattern(
        self, pattern: str, timeout_ms: int = 10000
    ) -> Optional[InterceptedResponse]:
        """Wartet, bis eine Response mit Pattern eintrifft."""
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) * 1000 < timeout_ms:
            matches = [r for r in self._intercepted if pattern in r.url]
            if matches:
                return matches[-1]
            await asyncio.sleep(0.1)
        return None


# === High-Level Convenience Functions ===


async def intercept_gmx_emails(page: Page, timeout_ms: int = 10000) -> list[dict]:
    """
    GMX-spezifisch: Faengt die Mail-API Responses ab.
    Robuster als DOM-Parsing der Email-Liste, da unabhaengig von Shadow DOM.
    """
    interceptor = NetworkInterceptor(page)
    interceptor.add_pattern("/mail", capture_body=True)
    interceptor.add_pattern("listMessages", capture_body=True)
    interceptor.add_pattern("/messages", capture_body=True)

    await interceptor.start()

    try:
        await page.wait_for_timeout(min(timeout_ms, 3000))

        emails = []
        for resp in interceptor.get_intercepted():
            if isinstance(resp.body, dict):
                for key in ["messages", "emails", "items", "data"]:
                    if key in resp.body and isinstance(resp.body[key], list):
                        emails.extend(resp.body[key])
                        break
            elif isinstance(resp.body, list):
                emails.extend(resp.body)

        logger.info("GMX emails intercepted", count=len(emails))
        return emails

    finally:
        await interceptor.stop()


async def intercept_api_data(
    page: Page,
    patterns: list[str],
    trigger_action: Optional[Callable] = None,
    timeout_ms: int = 10000,
) -> list[Any]:
    """
    Generische API-Interception.
    Optional: trigger_action wird ausgefuehrt, um den API-Call zu provozieren.
    """
    interceptor = NetworkInterceptor(page)
    for pattern in patterns:
        interceptor.add_pattern(pattern, capture_body=True)

    await interceptor.start()

    try:
        if trigger_action:
            await trigger_action()

        await page.wait_for_timeout(min(timeout_ms, 3000))

        results = []
        for resp in interceptor.get_intercepted():
            if isinstance(resp.body, (dict, list)):
                results.append(resp.body)

        return results

    finally:
        await interceptor.stop()
