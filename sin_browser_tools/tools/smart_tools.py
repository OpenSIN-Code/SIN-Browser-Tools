"""
High-Level Enterprise Tools -- Die neue Generation von Browser-Tools.
Ersetzen und erweitern die Basis-Tools um Enterprise-Faehigkeiten:
OOPIF-Support, Shadow-DOM-Piercing, Session-Management, PII-Redaction.
"""

from typing import Any, Optional
from urllib.parse import urlparse

from playwright.async_api import BrowserContext, Page
import structlog

from sin_browser_tools.core.frame_traversal import UnifiedFrameTraverser
from sin_browser_tools.core.spa_waker import SPAWaker
from sin_browser_tools.core.session_vault import SessionVault
from sin_browser_tools.core.pii_redaction import PIIRedactor
from sin_browser_tools.core.observability import TraceLogger
from sin_browser_tools.tools.network_intercept import intercept_api_data

logger = structlog.get_logger(__name__)


class SmartBrowserTools:
    """
    Enterprise-Tool-Suite mit OOPIF-Support, Shadow-DOM-Piercing,
    Session-Management und automatischer PII-Redaction.
    """

    def __init__(
        self,
        page: Page,
        context: Optional[BrowserContext] = None,
        tracer: Optional[TraceLogger] = None,
        redactor: Optional[PIIRedactor] = None,
    ):
        self.page = page
        self.context = context
        self.tracer = tracer or TraceLogger(enabled=False)
        self.redactor = redactor or PIIRedactor()
        self.traverser = UnifiedFrameTraverser(pierce_shadow=True)
        self.waker = SPAWaker()
        self.vault = SessionVault() if context else None

    async def smart_navigate(
        self,
        url: str,
        restore_session: bool = True,
        wait_for_stability: bool = True,
        close_popups: bool = True,
    ) -> dict:
        """
        Intelligente Navigation mit Session-Restore, Auto-Popup-Close
        und SID-Redirect-Detection.
        """
        async def _do():
            result: dict[str, Any] = {
                "url": url,
                "session_restored": False,
                "popups_closed": 0,
            }

            if restore_session and self.vault and self.context:
                domain = urlparse(url).netloc
                result["session_restored"] = await self.vault.restore_session(
                    self.context, domain
                )

            response = await self.page.goto(
                url, wait_until="domcontentloaded", timeout=30000
            )
            result["status"] = response.status if response else None
            result["final_url"] = self.page.url

            if self.vault:
                new_sid = await self.vault.detect_sid_redirect(self.page)
                if new_sid:
                    result["new_sid"] = new_sid

            if close_popups:
                result["popups_closed"] = await self.waker.close_popups(self.page)

            if wait_for_stability:
                await self.waker.wait_for_dom_stability(self.page)

            return result

        return await self.tracer.trace_tool_call(
            "smart_navigate", {"url": url}, _do, self.page
        )

    async def deep_snapshot(
        self,
        mode: str = "enterprise",
        pierce_shadow: bool = True,
        redact_pii: bool = True,
        include_html: bool = False,
    ) -> dict:
        """
        Tiefen-Snapshot ueber ALLE Frames, inkl. Shadow DOM.
        Optional mit automatischer PII-Redaction.

        Loest das GMX-OOPIF-Problem: Nutzt Playwright's native
        frame.accessibility.snapshot() statt new_cdp_session().
        """
        async def _do():
            traverser = UnifiedFrameTraverser(
                pierce_shadow=pierce_shadow, include_html=include_html
            )
            frames = await traverser.traverse(self.page)

            snapshot: dict[str, Any] = {
                "url": self.page.url,
                "title": await self.page.title(),
                "frame_count": len(frames),
                "frames": [],
            }

            for frame_info in frames:
                frame_data: dict[str, Any] = {
                    "url": frame_info.url,
                    "name": frame_info.name,
                    "is_main": frame_info.is_main,
                    "frame_type": frame_info.frame_type,
                    "ax_tree": frame_info.ax_tree,
                    "shadow_roots": frame_info.shadow_roots,
                    "shadow_count": len(frame_info.shadow_roots),
                }

                if redact_pii and frame_data["ax_tree"]:
                    frame_data["ax_tree"] = self.redactor.redact_ax_tree(
                        frame_data["ax_tree"]
                    )

                snapshot["frames"].append(frame_data)

            snapshot["aggregated_tree"] = traverser._aggregate_ax_trees(frames)
            if redact_pii:
                snapshot["aggregated_tree"] = self.redactor.redact_ax_tree(
                    snapshot["aggregated_tree"]
                )

            return snapshot

        return await self.tracer.trace_tool_call(
            "deep_snapshot",
            {"mode": mode, "pierce_shadow": pierce_shadow},
            _do,
            self.page,
        )

    async def smart_interact(
        self,
        selector: str,
        action: str = "click",
        intent: Optional[str] = None,
        wake_spa: bool = True,
        timeout_ms: int = 10000,
    ) -> dict:
        """
        Intelligente Interaktion mit SPA-Wake-Up und Frame-Traversal.
        actions: click, hover, focus, scroll_into_view
        """
        async def _do():
            if wake_spa:
                await self.waker.wait_for_dom_stability(self.page, timeout_ms=5000)

            target = await self.traverser.find_element_across_frames(
                self.page, selector
            )
            result: dict[str, Any] = {
                "success": True,
                "action": action,
                "selector": selector,
            }

            if not target:
                locator = self.page.locator(selector).first
                try:
                    await locator.wait_for(state="visible", timeout=timeout_ms)
                    frame_locator = locator
                except Exception as e:
                    result["success"] = False
                    result["error"] = f"Element not found: {e}"
                    return result
            else:
                frame, _element = target
                frame_locator = frame.locator(selector).first

            try:
                if action == "click":
                    await frame_locator.click()
                elif action == "hover":
                    await frame_locator.hover()
                elif action == "focus":
                    await frame_locator.focus()
                elif action == "scroll_into_view":
                    await frame_locator.scroll_into_view_if_needed()
                else:
                    raise ValueError(f"Unknown action: {action}")

                await self.page.wait_for_timeout(500)
                await self.waker.wait_for_dom_stability(self.page, timeout_ms=3000)

            except Exception as e:
                result["success"] = False
                result["error"] = str(e)

            return result

        return await self.tracer.trace_tool_call(
            "smart_interact",
            {"selector": selector, "action": action, "intent": intent},
            _do,
            self.page,
        )

    async def extract_structured_data(
        self,
        api_patterns: list[str],
        trigger_selector: Optional[str] = None,
        timeout_ms: int = 10000,
    ) -> list[Any]:
        """
        Extrahiert strukturierte Daten via Network-Interception.
        Die robuste Alternative zu fragilem DOM-Parsing.
        """
        async def _do():
            async def trigger():
                if trigger_selector:
                    await self.smart_interact(trigger_selector, "click", wake_spa=True)

            return await intercept_api_data(
                self.page, api_patterns, trigger, timeout_ms
            )

        return await self.tracer.trace_tool_call(
            "extract_structured_data",
            {"patterns": api_patterns, "trigger": trigger_selector},
            _do,
            self.page,
        )

    async def wait_for_stable_dom(self, timeout_ms: int = 15000) -> bool:
        """Wartet auf DOM-Stabilitaet."""
        return await self.waker.wait_for_dom_stability(self.page, timeout_ms)

    async def close_popups(self) -> int:
        """Schliesst typische Popups (Cookie-Banner, Newsletter)."""
        return await self.waker.close_popups(self.page)
