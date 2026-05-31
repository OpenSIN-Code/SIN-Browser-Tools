"""
Gehärteter BrowserManager mit garantierter Cleanup, Zombie-Protection
und Enterprise-Features (Session Vault, Observability).
"""

import asyncio
import os
import signal
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)
import structlog

from sin_browser_tools.core.session_vault import SessionVault
from sin_browser_tools.core.observability import TraceLogger

logger = structlog.get_logger(__name__)


class BrowserManager:
    """Enterprise Browser Manager mit garantierter Prozess-Sicherheit."""

    def __init__(
        self,
        headless: bool = True,
        user_data_dir: Optional[str] = None,
        proxy: Optional[dict] = None,
        vault_path: str = "./.sin_vault",
        trace_dir: str = "./.sin_traces",
        stealth: bool = True,
    ):
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.proxy = proxy
        self.stealth = stealth
        self.vault = SessionVault(vault_path)
        self.tracer = TraceLogger(trace_dir)

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        self._started = False

        self._install_signal_handlers()

    def _install_signal_handlers(self):
        """Garantiert Cleanup bei SIGTERM/SIGINT."""
        def _handler(signum, frame):
            logger.warning("Signal received, triggering cleanup", signal=signum)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.cleanup())
            except RuntimeError:
                pass

        try:
            signal.signal(signal.SIGTERM, _handler)
            signal.signal(signal.SIGINT, _handler)
        except (ValueError, AttributeError):
            pass

    async def start_local(self) -> "BrowserManager":
        """Startet lokalen Chromium-Browser mit Enterprise-Defaults."""
        async with self._lock:
            if self._started:
                return self

            self._playwright = await async_playwright().start()

            launch_args = {
                "headless": self.headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                    "--start-maximized",
                ],
            }

            if self.proxy:
                launch_args["proxy"] = self.proxy

            if self.user_data_dir:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    self.user_data_dir,
                    **launch_args,
                    accept_downloads=True,
                    bypass_csp=True,
                    ignore_https_errors=True,
                )
                self._page = (
                    self._context.pages[0]
                    if self._context.pages
                    else await self._context.new_page()
                )
            else:
                self._browser = await self._playwright.chromium.launch(**launch_args)
                self._context = await self._browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    locale="de-DE",
                    timezone_id="Europe/Berlin",
                    accept_downloads=True,
                    bypass_csp=True,
                    ignore_https_errors=True,
                )
                self._page = await self._context.new_page()

            if self.stealth:
                await self._apply_stealth(self._page)

            self._started = True
            logger.info("BrowserManager started", headless=self.headless)
            return self

    async def _apply_stealth(self, page: Page):
        """Injiziert Stealth-Patches gegen Bot-Detection."""
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['de-DE', 'de', 'en-US', 'en'] });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);
        """)

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("BrowserManager not started. Call start_local() first.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if not self._context:
            raise RuntimeError("BrowserManager not started.")
        return self._context

    async def new_page(self) -> Page:
        """Erstellt eine neue Page im gleichen Context (teilt Cookies)."""
        return await self.context.new_page()

    async def cleanup(self):
        """
        Garantiertes Cleanup -- wird IMMER ausgeführt, auch bei Exceptions.
        Jeder Teardown-Schritt ist unabhängig gesichert, damit kein
        Chromium-Zombie-Prozess bei einem Partial-Failure hängen bleibt.
        """
        async with self._lock:
            if not self._started:
                return

            logger.info("Cleanup initiated")
            errors = []

            try:
                if self._context:
                    await self._context.close()
            except Exception as e:
                errors.append(f"context.close: {e}")

            try:
                if self._browser:
                    await self._browser.close()
            except Exception as e:
                errors.append(f"browser.close: {e}")

            try:
                if self._playwright:
                    await self._playwright.stop()
            except Exception as e:
                errors.append(f"playwright.stop: {e}")

            await self._kill_zombie_processes()

            self._started = False
            self._context = None
            self._browser = None
            self._playwright = None
            self._page = None

            if errors:
                logger.warning("Cleanup completed with errors", errors=errors)
            else:
                logger.info("Cleanup completed successfully")

    async def _kill_zombie_processes(self):
        """Killed verwaiste Chromium/Playwright-Prozesse."""
        try:
            if os.name == "posix":
                proc = await asyncio.create_subprocess_shell(
                    "pkill -f 'chromium.*playwright' 2>/dev/null || true"
                )
                await proc.wait()
        except Exception as e:
            logger.debug("Zombie kill failed", error=str(e))

    @asynccontextmanager
    async def session(self):
        """
        Context-Manager für garantiertes Cleanup.

        Usage::

            async with BrowserManager().session() as mgr:
                await mgr.page.goto("...")
        """
        try:
            await self.start_local()
            yield self
        finally:
            await self.cleanup()

    async def save_session(self, domain: str):
        """Speichert aktuelle Session in Vault."""
        await self.vault.save_session(self.context, domain)

    async def restore_session(self, domain: str) -> bool:
        """Stellt Session aus Vault wieder her."""
        return await self.vault.restore_session(self.context, domain)

    async def __aenter__(self):
        return await self.start_local()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
