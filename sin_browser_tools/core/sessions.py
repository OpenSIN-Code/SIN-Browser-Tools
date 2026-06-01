"""Parallele, ISOLIERTE Browser-Sessions (Multi-Context).

Jeder benannte "Context" ist ein eigener Playwright-BrowserContext: vollstaendig
getrennte Cookies, localStorage, sessionStorage, Cache und Auth. Das ist die
Grundlage fuer:
  - Vergleich zweier Seiten nebeneinander
  - parallele Suchen / Scrapes
  - eingeloggt vs. ausgeloggt gleichzeitig
  - A/B-Testing

Designprinzip: Beim "switch" setzen wir ``_context`` und ``_page`` der aktiven
BrowserManager-Instanz um. Dadurch arbeiten ALLE bestehenden Tools (navigation,
interaction, extraction, ...) automatisch auf der gewechselten Session, ohne dass
sie das Multi-Context-Konzept kennen muessen.

Hinweis: Mehrere Contexts brauchen einen echten ``browser`` (start_local ohne
user_data_dir, oder CDP). Bei ``launch_persistent_context`` (user_data_dir) gibt
es nur einen einzigen Context -> die Create-Operation liefert dann einen klaren
Fehler statt zu crashen.
"""

from typing import Optional

import structlog
from playwright.async_api import BrowserContext, Page

logger = structlog.get_logger(__name__)


# Sinnvolle Defaults fuer neue Contexts -- spiegeln die Defaults aus
# BrowserManager.start_local() wider, damit parallele Sessions sich wie die
# Haupt-Session verhalten (Locale, UA, Downloads, CSP-Bypass).
_DEFAULT_CONTEXT_OPTS = {
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "locale": "de-DE",
    "timezone_id": "Europe/Berlin",
    "accept_downloads": True,
    "bypass_csp": True,
    "ignore_https_errors": True,
}


class SessionManager:
    """Verwaltet mehrere benannte, isolierte BrowserContexts fuer eine
    BrowserManager-Instanz."""

    def __init__(self, mgr):
        # Referenz auf die BrowserManager-Instanz (kein Import-Zyklus, da nur
        # zur Laufzeit uebergeben).
        self._mgr = mgr
        self._contexts: dict[str, BrowserContext] = {}
        # Aktive Page PRO Context, damit ein switch den zuletzt genutzten Tab
        # dieser Session wiederherstellt statt immer pages[0].
        self._active_pages: dict[str, Page] = {}
        self._active_name: Optional[str] = None

    # --- interne Helfer ------------------------------------------------------

    def _ensure_default_registered(self) -> None:
        """Registriert den beim Start angelegten Context als 'default'.

        Idempotent; lazy aufgerufen, damit auch nach connect_cdp() der erste
        Context als 'default' auftaucht.
        """
        ctx = self._mgr._context
        if ctx is None:
            return
        if "default" not in self._contexts:
            self._contexts["default"] = ctx
            self._active_pages["default"] = self._mgr._page
            if self._active_name is None:
                self._active_name = "default"
        # Falls der Nutzer den default-Context-Namen nie explizit gewechselt hat,
        # halten wir dessen aktive Page aktuell.
        if self._active_name == "default":
            self._active_pages["default"] = self._mgr._page

    def _sync_active_into_manager(self, name: str) -> None:
        """Setzt _context/_page der Instanz auf die benannte Session."""
        ctx = self._contexts[name]
        page = self._active_pages.get(name)
        if page is None or page.is_closed():
            # zuletzt genutzte Page weg -> erste offene Page nehmen / neue oeffnen
            page = ctx.pages[0] if ctx.pages else None
        self._mgr._context = ctx
        self._mgr._page = page
        self._active_name = name
        if page is not None:
            self._active_pages[name] = page
        # @eN-Refs sind page-lokal -> nach Session-Wechsel ungueltig.
        reg = self._mgr.__dict__.get("_registry_stub")
        if reg is not None:
            reg.clear()
        # Dialog-Listener an die (ggf. neue) aktive Page haengen.
        try:
            self._mgr._setup_dialog_handler()
        except Exception:
            pass

    # --- oeffentliche API ----------------------------------------------------

    async def create_context(self, name: str, **opts) -> dict:
        """Neuen isolierten Context mit eigener Start-Page anlegen."""
        self._ensure_default_registered()

        browser = self._mgr._browser
        if browser is None:
            return {
                "status": "error",
                "error": (
                    "Multiple contexts require a real browser. This session was "
                    "started with a persistent user_data_dir (single context only). "
                    "Restart without user_data_dir, or use tabs (browser_new_tab)."
                ),
            }
        if name in self._contexts:
            return {"status": "error", "error": "context {!r} already exists".format(name)}
        if not name or name.strip() != name:
            return {"status": "error", "error": "context name must be non-empty and unstripped"}

        merged = dict(_DEFAULT_CONTEXT_OPTS)
        merged.update(opts or {})
        try:
            ctx = await browser.new_context(**merged)
            page = await ctx.new_page()
        except Exception as e:
            return {"status": "error", "error": str(e)}

        if getattr(self._mgr, "stealth", False):
            try:
                await self._mgr._apply_stealth(page)
            except Exception:
                pass

        self._contexts[name] = ctx
        self._active_pages[name] = page
        logger.info("session context created", name=name, total=len(self._contexts))
        return {
            "status": "ok",
            "name": name,
            "total_contexts": len(self._contexts),
            "isolated": True,
        }

    def list_contexts(self) -> dict:
        self._ensure_default_registered()
        out = []
        for name, ctx in self._contexts.items():
            try:
                pages = ctx.pages
                url = pages[0].url if pages else None
                tab_count = len(pages)
            except Exception:
                url, tab_count = None, 0
            out.append({
                "name": name,
                "active": name == self._active_name,
                "tabs": tab_count,
                "active_url": (self._active_pages.get(name).url
                               if self._active_pages.get(name)
                               and not self._active_pages[name].is_closed()
                               else url),
            })
        return {"status": "ok", "active": self._active_name, "contexts": out}

    async def switch_context(self, name: str) -> dict:
        self._ensure_default_registered()
        if name not in self._contexts:
            return {"status": "error", "error": "no context named {!r}".format(name),
                    "available": list(self._contexts.keys())}
        self._sync_active_into_manager(name)
        return {"status": "ok", "active": name,
                "active_url": self._mgr._page.url if self._mgr._page else None}

    async def close_context(self, name: str) -> dict:
        self._ensure_default_registered()
        if name not in self._contexts:
            return {"status": "error", "error": "no context named {!r}".format(name)}
        if name == "default" and len(self._contexts) > 1:
            return {"status": "error",
                    "error": "refusing to close the 'default' context while others exist; "
                             "switch away and close the others, or close 'default' last"}
        ctx = self._contexts[name]
        was_active = name == self._active_name
        try:
            await ctx.close()
        except Exception as e:
            return {"status": "error", "error": str(e)}
        del self._contexts[name]
        self._active_pages.pop(name, None)

        # Falls die aktive Session geschlossen wurde, auf eine andere wechseln.
        if was_active:
            if self._contexts:
                fallback = next(iter(self._contexts))
                self._sync_active_into_manager(fallback)
            else:
                self._active_name = None
                self._mgr._context = None
                self._mgr._page = None
        return {"status": "ok", "closed": name,
                "remaining": list(self._contexts.keys()),
                "active": self._active_name}

    async def parallel_navigate(self, sessions: list[dict], timeout: float = 30000) -> dict:
        """Mehrere Sessions GLEICHZEITIG navigieren.

        ``sessions`` = Liste von ``{"name": str, "url": str}``. Fehlende Contexts
        werden automatisch angelegt. Liefert pro Session Status/URL/Titel. Der
        zuvor aktive Context bleibt nach dem Aufruf aktiv.
        """
        import asyncio

        self._ensure_default_registered()
        previously_active = self._active_name

        # 1) fehlende Contexts anlegen (seriell -- billig, vermeidet Races auf dict)
        for s in sessions:
            name = s.get("name")
            if not name:
                return {"status": "error", "error": "each session needs a 'name'"}
            if name not in self._contexts:
                created = await self.create_context(name)
                if created.get("status") != "ok":
                    return {"status": "error", "error": "create {!r} failed: {}".format(
                        name, created.get("error"))}

        # 2) parallel navigieren -- jede Page in ihrem eigenen Context.
        async def _go(name: str, url: str) -> dict:
            page = self._active_pages.get(name)
            if page is None or page.is_closed():
                ctx = self._contexts[name]
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                self._active_pages[name] = page
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                title = await page.title()
                return {"name": name, "status": resp.status if resp else "unknown",
                        "url": page.url, "title": title}
            except Exception as e:
                return {"name": name, "status": "error", "url": url, "error": str(e)}

        results = await asyncio.gather(
            *[_go(s["name"], s["url"]) for s in sessions],
            return_exceptions=False,
        )

        # 3) vorher aktive Session wiederherstellen, damit der Aufrufer nicht
        #    ueberraschend auf einer anderen Session landet.
        if previously_active and previously_active in self._contexts:
            self._sync_active_into_manager(previously_active)

        return {"status": "ok", "results": list(results), "active": self._active_name}

    async def close_all(self) -> None:
        """Alle nicht-default Contexts schliessen (vom Cleanup genutzt)."""
        for name in [n for n in self._contexts if n != "default"]:
            try:
                await self._contexts[name].close()
            except Exception:
                pass
        self._contexts = {k: v for k, v in self._contexts.items() if k == "default"}
        self._active_pages = {k: v for k, v in self._active_pages.items() if k == "default"}
