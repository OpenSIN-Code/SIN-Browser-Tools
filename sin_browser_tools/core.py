import asyncio
import json
import logging
import weakref
import websockets
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, ElementHandle

logger = logging.getLogger(__name__)

class ElementRegistry:
    """Maps stable ref-ids (@e1, @e2, ...) to either a Playwright ElementHandle
    (high-level API) or a CDP descriptor dict (low-level API, required for
    OOPIF / Shadow-DOM elements that Playwright cannot resolve via selectors).

    CDP descriptors carry:
      - ``backendDOMNodeId``: the node id, valid ONLY on its owning target.
      - ``role`` / ``name``: used to rebuild an accessible Playwright locator.
      - ``frame``: the Playwright Frame the node lives in. Required because
        backendDOMNodeIds are target-local and OOPIF input must be routed
        through the owning frame's CDP session / locator."""

    def __init__(self):
        self.elements: Dict[str, Any] = {}
        self.counter = 0
    
    def clear(self):
        self.elements.clear()
        self.counter = 0
    
    def register(self, value: Any) -> str:
        """Register a Playwright ElementHandle or a CDP descriptor dict.

        Returns the generated ref-id (e.g. ``@e1``).
        """
        self.counter += 1
        ref_id = f"@e{self.counter}"
        self.elements[ref_id] = value
        return ref_id
    
    def get(self, ref_id: str) -> Optional[Any]:
        return self.elements.get(ref_id)

class SINBrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.registry = ElementRegistry()
        self._dialog_queue: asyncio.Queue = asyncio.Queue()
        # The dialog currently waiting to be accepted/dismissed. Held separately
        # from the queue so that browser_wait_for_dialog can PEEK at it without
        # consuming it -- otherwise a subsequent browser_dialog("accept") would
        # find an empty queue and the native dialog would hang the page forever.
        self._pending_dialog: Optional[dict] = None
        # Pages that already have a dialog listener attached, so switching tabs
        # never stacks duplicate handlers (which would enqueue one dialog N times).
        # A WeakSet keyed on the Page objects themselves -- NOT id(page) -- because
        # CPython reuses the id of a closed/GC'd page for a brand-new page, which
        # would make _setup_dialog_handler wrongly skip attaching a listener to a
        # genuinely new tab and silently drop all of its dialogs.
        self._dialog_pages: "weakref.WeakSet[Page]" = weakref.WeakSet()

    async def start_local(self, headless: bool = True):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.page = await self.context.new_page()
        self._setup_dialog_handler()

    async def connect_cdp(self, cdp_url: str):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.connect_over_cdp(cdp_url)
        self.context = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        self._setup_dialog_handler()

    def _setup_dialog_handler(self):
        # Attach at most one dialog listener per page. Without this guard,
        # every set_active_page() call (tab open/switch/close) would add another
        # listener to the same page and a single alert/confirm would be enqueued
        # multiple times, corrupting the dialog queue.
        if self.page is None or self.page in self._dialog_pages:
            return

        async def handle_dialog(dialog):
            await self._dialog_queue.put({
                "type": dialog.type,
                "message": dialog.message,
                "default_value": dialog.default_value,
                "dialog": dialog
            })
        self.page.on("dialog", handle_dialog)
        self._dialog_pages.add(self.page)

    def set_active_page(self, page: Optional[Page]):
        """Make ``page`` the active page and (re)attach the dialog handler.

        Used by the tab-management tools when switching/opening/closing tabs so
        that subsequent actions and dialog capture target the correct page.

        Switching the active page also invalidates every @eN ref: refs are
        page-local, so a ref captured on the old tab must not be clicked on the
        new one. Callers must browser_snapshot again after switching tabs.
        """
        self.page = page
        if page is None:
            return
        self.registry.clear()
        self._setup_dialog_handler()

    async def get_next_dialog(self, timeout: float = 5.0, consume: bool = True) -> Optional[dict]:
        """Return the next pending native dialog.

        - ``consume=True`` (default, used by ``browser_dialog``): hand the dialog
          to the caller and clear it so it can be accepted/dismissed exactly once.
        - ``consume=False`` (used by ``browser_wait_for_dialog``): PEEK only. The
          dialog stays pending so a follow-up ``browser_dialog("accept")`` can
          still act on the very same dialog instead of getting an empty queue.

        A previously peeked dialog is cached in ``_pending_dialog`` so repeated
        waits/acts always refer to the same live ``Dialog`` object.
        """
        if self._pending_dialog is None:
            try:
                self._pending_dialog = await asyncio.wait_for(
                    self._dialog_queue.get(), timeout=timeout
                )
            except asyncio.TimeoutError:
                return None

        dialog_info = self._pending_dialog
        if consume:
            self._pending_dialog = None
        return dialog_info

    async def cleanup(self):
        """Tear down the browser and reset all state. Safe to call multiple times.

        Each teardown step is guarded independently so that a failure closing the
        browser still stops the Playwright driver -- otherwise a half-failed
        cleanup would leak Chromium processes (zombies) that pile up under load
        and eventually OOM-kill the container.
        """
        try:
            if self.browser:
                await self.browser.close()
        except Exception as e:  # noqa: BLE001 - never let teardown raise
            logger.warning("Error closing browser during cleanup: %s", e)
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:  # noqa: BLE001
            logger.warning("Error stopping Playwright during cleanup: %s", e)
        # Reset all state so a subsequent start_local()/connect_cdp() on the same
        # manager instance begins from a clean slate.
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self._pending_dialog = None
        self._dialog_pages.clear()
        self.registry.clear()

    async def __aenter__(self) -> "SINBrowserManager":
        """Allow ``async with SINBrowserManager() as m:`` so cleanup() is
        GUARANTEED even when an action raises mid-flow. Auto-starts a local
        browser if one is not already running."""
        if self.page is None:
            await self.start_local()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.cleanup()
        return False

    @staticmethod
    async def scan_cdp_ports(host: str = "localhost", ports: List[int] = None) -> Optional[str]:
        if ports is None:
            ports = [9222, 9223, 9224, 9225, 9229, 9230, 9333]
        
        for port in ports:
            try:
                uri = f"ws://{host}:{port}"
                async with websockets.connect(uri, open_timeout=1.0) as ws:
                    await ws.send(json.dumps({"id": 1, "method": "Browser.getVersion"}))
                    response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(response)
                    if "result" in data:
                        logger.info(f"Found Chrome CDP on {host}:{port}")
                        return f"http://{host}:{port}"
            except Exception:
                continue
        return None

manager = SINBrowserManager()
