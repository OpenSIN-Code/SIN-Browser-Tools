import asyncio
import json
import logging
import websockets
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, ElementHandle

logger = logging.getLogger(__name__)

class ElementRegistry:
    """Maps stable ref-ids (@e1, @e2, ...) to either a Playwright ElementHandle
    (high-level API) or a CDP descriptor dict containing a ``backendDOMNodeId``
    (low-level API, required for OOPIF / Shadow-DOM elements that Playwright
    cannot resolve)."""

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
        # Pages that already have a dialog listener attached, so switching tabs
        # never stacks duplicate handlers (which would enqueue one dialog N times).
        self._dialog_pages: "set[int]" = set()

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
        if self.page is None or id(self.page) in self._dialog_pages:
            return

        async def handle_dialog(dialog):
            await self._dialog_queue.put({
                "type": dialog.type,
                "message": dialog.message,
                "default_value": dialog.default_value,
                "dialog": dialog
            })
        self.page.on("dialog", handle_dialog)
        self._dialog_pages.add(id(self.page))

    def set_active_page(self, page: Page):
        """Make ``page`` the active page and (re)attach the dialog handler.

        Used by the tab-management tools when switching/opening/closing tabs so
        that subsequent actions and dialog capture target the correct page.
        """
        self.page = page
        self._setup_dialog_handler()

    async def get_next_dialog(self, timeout: float = 5.0) -> Optional[dict]:
        try:
            return await asyncio.wait_for(self._dialog_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def cleanup(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        # Reset all state so a subsequent start_local()/connect_cdp() on the same
        # manager instance begins from a clean slate.
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self._dialog_pages.clear()
        self.registry.clear()

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
