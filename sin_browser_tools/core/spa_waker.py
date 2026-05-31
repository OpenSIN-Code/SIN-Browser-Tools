"""
SPA Waker -- Zwingt moderne SPAs dazu, ihre Inhalte zu rendern.
Loest das GMX-Email-Listen-Problem durch gezielte Heuristiken.
"""

import asyncio
from typing import Optional

from playwright.async_api import Page
import structlog

logger = structlog.get_logger(__name__)


class SPAWaker:
    """
    Provoziert das Rendering von SPA-Inhalten durch simulierte
    User-Interaktionen und intelligentes DOM-Stability-Waiting.
    """

    def __init__(self, default_timeout_ms: int = 15000):
        self.default_timeout_ms = default_timeout_ms

    async def wait_for_dom_stability(
        self, page: Page, timeout_ms: int = 10000, stable_threshold: int = 3
    ) -> bool:
        """
        Wartet, bis sich der DOM nicht mehr aendert.
        Robuster als wait_for_load_state('networkidle'), weil es den
        tatsaechlichen DOM-Zustand prueft statt nur den Netzwerk-Idle-State.
        """
        prev_hash = ""
        stable_count = 0
        start = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start) * 1000 < timeout_ms:
            try:
                curr_hash = await page.evaluate("""
                    () => {
                        const elements = document.querySelectorAll('*');
                        return `${elements.length}_${document.body.innerHTML.length}`;
                    }
                """)
                if curr_hash == prev_hash:
                    stable_count += 1
                    if stable_count >= stable_threshold:
                        logger.debug("DOM stabilized", stable_count=stable_count)
                        return True
                else:
                    stable_count = 0
                    prev_hash = curr_hash
            except Exception as e:
                logger.debug("Stability check failed", error=str(e))

            await page.wait_for_timeout(500)

        logger.warning("DOM stability timeout reached", timeout_ms=timeout_ms)
        return False

    async def ghost_interact(self, page: Page):
        """
        Simuliert minimale User-Praesenz ohne sichtbare Seiteneffekte.
        Viele SPAs (und insbesondere Web Components) rendern erst bei
        Mouse-Movement oder Focus-Events.
        """
        try:
            await page.mouse.move(500, 400)
            await page.wait_for_timeout(200)
            await page.mouse.move(600, 450)
            await page.wait_for_timeout(200)
            await page.keyboard.press("Tab")
            await page.wait_for_timeout(100)
            await page.keyboard.press("Tab")
        except Exception as e:
            logger.debug("Ghost interaction failed", error=str(e))

    async def wake_gmx_mail(self, page: Page, timeout_ms: Optional[int] = None) -> bool:
        """
        GMX-spezifische Heuristik, um die Email-Liste zu mounten.

        GMX-Architektur:
        - iframe[name='lps'] ist ein empty shell, der erst bei Navigation befuellt wird
        - Die Email-Liste ist ein Web Component (moeglicherweise mit closed Shadow DOM)
        - Sie wird erst nach User-Interaction oder explizitem 'E-Mail'-Tab-Click gemountet
        """
        timeout = timeout_ms or self.default_timeout_ms
        logger.info("Waking up GMX mail UI")

        # Ghost-Interactions zuerst
        await self.ghost_interact(page)

        # Suche und klicke den "E-Mail" Tab im Navigator
        try:
            mail_tab = page.get_by_role("link", name="E-Mail").first
            if await mail_tab.is_visible(timeout=3000):
                await mail_tab.click()
                await page.wait_for_timeout(2000)
        except Exception:
            pass

        # DOM-Stabilitaet abwarten
        return await self.wait_for_dom_stability(page, timeout)

    async def wake_generic_spa(self, page: Page, timeout_ms: Optional[int] = None) -> bool:
        """
        Generische SPA-Heuristik fuer React/Vue/Angular Apps.
        """
        timeout = timeout_ms or self.default_timeout_ms

        await self.ghost_interact(page)

        # Warte auf React-Hydration (falls vorhanden)
        try:
            await page.evaluate("""
                () => new Promise(resolve => {
                    if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
                        resolve();
                    } else {
                        setTimeout(resolve, 2000);
                    }
                })
            """)
        except Exception:
            pass

        return await self.wait_for_dom_stability(page, timeout)

    async def trigger_lazy_load(self, page: Page, scroll_steps: int = 3):
        """Scroll-Trigger fuer Lazy-Loading-Inhalte."""
        for i in range(scroll_steps):
            await page.evaluate(f"window.scrollBy(0, {400 * (i + 1)})")
            await page.wait_for_timeout(800)
        await page.evaluate("window.scrollTo(0, 0)")

    async def close_popups(self, page: Page) -> int:
        """
        Erkennt und schliesst typische Popups (Cookie-Banner, Newsletter).
        Gibt Anzahl der geschlossenen Popups zurueck.
        """
        popup_selectors = [
            'button:has-text("Akzeptieren")',
            'button:has-text("Accept all")',
            'button:has-text("Alle akzeptieren")',
            'button:has-text("Zustimmen")',
            'button:has-text("I agree")',
            '[data-testid="cookie-accept"]',
            "#onetrust-accept-btn-handler",
            'button:has-text("Schliessen")',
            'button[aria-label="Close"]',
            'button[aria-label="Schliessen"]',
            ".modal-close",
            ".popup-close",
        ]

        closed_count = 0
        for selector in popup_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=500):
                    await btn.click()
                    closed_count += 1
                    await page.wait_for_timeout(300)
            except Exception:
                continue

        if closed_count:
            logger.info("Closed popups", count=closed_count)
        return closed_count
