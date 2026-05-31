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
        # PID des lokal gestarteten Chromium -- nur gesetzt, wenn WIR den Prozess
        # gestartet haben (nicht bei connect_cdp). Wird fuer gezieltes,
        # session-lokales Zombie-Cleanup verwendet.
        self._browser_pid: Optional[int] = None
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

            self._browser_pid = self._resolve_browser_pid()

            self._started = True
            logger.info(
                "BrowserManager started",
                headless=self.headless,
                browser_pid=self._browser_pid,
            )
            return self

    def _resolve_browser_pid(self) -> Optional[int]:
        """Versucht, die OS-PID des gestarteten Chromium-Prozesses zu ermitteln.

        Playwright legt die PID je nach Version unter
        ``browser._impl_obj._connection._transport._proc`` oder aehnlich ab.
        Schlaegt das fehl, geben wir None zurueck und das Cleanup faellt
        sicher auf 'nichts killen' zurueck (besser als fremde Prozesse killen).
        """
        candidates = []
        try:
            browser = self._browser
            if browser is not None:
                impl = getattr(browser, "_impl_obj", None)
                conn = getattr(impl, "_connection", None)
                transport = getattr(conn, "_transport", None)
                proc = getattr(transport, "_proc", None)
                if proc is not None and getattr(proc, "pid", None):
                    candidates.append(proc.pid)
        except Exception:
            pass
        # Persistent-context-Launch: Browser haengt am Context.
        try:
            if not candidates and self._context is not None:
                impl = getattr(self._context, "_impl_obj", None)
                br = getattr(impl, "_browser", None)
                conn = getattr(getattr(br, "_connection", None), "_transport", None)
                proc = getattr(conn, "_proc", None)
                if proc is not None and getattr(proc, "pid", None):
                    candidates.append(proc.pid)
        except Exception:
            pass
        return candidates[0] if candidates else None

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
            self._browser_pid = None

            if errors:
                logger.warning("Cleanup completed with errors", errors=errors)
            else:
                logger.info("Cleanup completed successfully")

    async def _kill_zombie_processes(self):
        """Killed NUR den von DIESEM Manager gestarteten Chromium-Prozessbaum.

        BUGFIX: Frueher lief hier ein globales
            pkill -f 'chromium.*playwright'
        Das killt ALLE Chromium-Prozesse im Container -- in einem
        Kubernetes-Pod mit mehreren parallelen BrowserManager-Sessions reisst
        das Cleanup einer Session also die Browser ALLER anderen Sessions mit.
        Wir killen jetzt gezielt nur unseren eigenen Browser-PID-Baum.

        Bei einem ueber CDP verbundenen (remote) Browser starten WIR den Prozess
        nicht -- dann darf auch nichts gekillt werden.
        """
        pid = self._browser_pid
        if pid is None:
            return
        try:
            if os.name == "posix":
                # SIGTERM an den gesamten Prozessbaum (negativer PID = Prozessgruppe
                # falls vorhanden; sonst direkter PID). pkill -P killt Kinder.
                proc = await asyncio.create_subprocess_shell(
                    f"pkill -TERM -P {pid} 2>/dev/null; kill -TERM {pid} 2>/dev/null || true"
                )
                await proc.wait()
        except Exception as e:
            logger.debug("Zombie kill failed", pid=pid, error=str(e))

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

    async def connect_cdp(self, endpoint_url: str) -> "BrowserManager":
        """
        Verbindet sich mit einem bereits laufenden Chrome/Chromium ueber CDP.

        Typischer Anwendungsfall: Chrome wurde mit
          --remote-debugging-port=9222
        gestartet und soll remote gesteuert werden, z.B. um eine aktive
        GMX-Session zu uebernehmen ohne neu einzuloggen.

        Usage::

            mgr = BrowserManager(headless=False)
            await mgr.connect_cdp("http://127.0.0.1:9222")
            for ctx in mgr._browser.contexts:
                for page in ctx.pages:
                    if "navigator.gmx.net" in page.url:
                        mgr.set_active_page(page)
        """
        async with self._lock:
            if self._started:
                return self

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(
                endpoint_url
            )

            # Setze ersten verfuegbaren Context + Page als aktiv
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
                pages = self._context.pages
                if pages:
                    self._page = pages[0]
            else:
                # Fallback: neuen Context aufmachen (sollte bei CDP-Connect selten sein)
                self._context = await self._browser.new_context()
                self._page = await self._context.new_page()

            self._started = True
            logger.info(
                "BrowserManager connected via CDP",
                endpoint=endpoint_url,
                contexts=len(self._browser.contexts),
            )
            return self

    def set_active_page(self, page: Page) -> None:
        """
        Setzt eine bestehende Playwright-Page als aktive Page des Managers.

        Wird benoetigt nach connect_cdp(), wenn man einen bestimmten Tab
        (z.B. den GMX-Tab) als aktiven Tab setzen will.

        Loescht automatisch alle @eN-Refs aus der Registry (falls vorhanden),
        da Refs seitenlokal sind und nach einem Tab-Wechsel nicht mehr gueltig.
        """
        self._page = page
        # Sicherstellen, dass der Context auch zum neuen Tab passt
        if page.context is not self._context:
            self._context = page.context
        # @eN-Refs sind seitenlokal (backendDOMNodeIds gelten nur im Target der
        # Snapshot-Page). Nach einem Tab-Wechsel zeigen sie auf den falschen Tab.
        # Daher hier die Registry leeren -- der Aufrufer muss neu snapshotten.
        reg = self.__dict__.get("_registry_stub")
        if reg is not None:
            reg.clear()

    def clear_active_page(self) -> None:
        """Setzt die aktive Page auf None (z.B. nachdem der letzte Tab zuging).

        Wird benoetigt, weil ``page`` eine read-only Property ist und nicht
        direkt auf None gesetzt werden kann.
        """
        self._page = None
        reg = self.__dict__.get("_registry_stub")
        if reg is not None:
            reg.clear()

    @property
    def active_page(self) -> Optional[Page]:
        """Wie ``page``, wirft aber NICHT, wenn keine Page aktiv ist."""
        return self._page

    @property
    def browser(self) -> Optional[Browser]:
        """Gibt den zugrundeliegenden Playwright-Browser zurueck."""
        return self._browser

    async def __aenter__(self):
        return await self.start_local()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()


# ---------------------------------------------------------------------------
# Singleton-Instanz fuer Rueckwaertskompatibilitaet mit v1.x
#
# Die alten Tools (tools/accessibility.py, tools/interaction.py, ...) importieren:
#   from sin_browser_tools.core import manager          # Modul-Import
#   manager.page, manager.registry, manager.browser     # Singleton-Attribute
#
# In v2.0 gibt es nur noch die BrowserManager-Klasse. Dieses Adapter-Objekt
# schlaegt alle Attribut-Zugriffe auf die aktive BrowserManager-Instanz durch
# und stellt sicher, dass v1.x-Tools ohne Code-Aenderungen weiter funktionieren.
# ---------------------------------------------------------------------------

class _ManagerProxy:
    """
    Drop-in-Ersatz fuer den v1.x manager-Singleton.

    Transparentes Proxy-Objekt: alle Attribut-Zugriffe und Methoden-Calls
    werden an die zugrunde liegende BrowserManager-Instanz delegiert.
    Neue Instanzen koennen per manager._set_instance(mgr) registriert werden.
    """

    def __init__(self):
        self._instance: Optional[BrowserManager] = None

    def _set_instance(self, mgr: BrowserManager) -> None:
        """Registriert eine BrowserManager-Instanz als aktiven Singleton."""
        self._instance = mgr

    def _require(self) -> BrowserManager:
        if self._instance is None:
            raise RuntimeError(
                "sin_browser_tools: Kein aktiver BrowserManager registriert.\n"
                "Loesungen:\n"
                "  (A) await manager.start_local()\n"
                "  (B) await manager.connect_cdp('http://127.0.0.1:9222')\n"
                "  (C) async with BrowserManager() as mgr: manager._set_instance(mgr)"
            )
        return self._instance

    # --- Passthrough-Properties fuer v1.x-Kompatibilitaet ---

    @property
    def page(self) -> Page:
        return self._require()._page  # type: ignore[return-value]

    @property
    def context(self) -> BrowserContext:
        return self._require()._context  # type: ignore[return-value]

    @property
    def browser(self):
        return self._require()._browser

    @property
    def playwright(self):
        return self._require()._playwright

    # registry wird von den v1.x-tools benoetigt -- in v2.0 nicht mehr Teil
    # des Managers, daher haengen wir EINE persistente Registry an die aktive
    # BrowserManager-Instanz.
    #
    # BUGFIX: Frueher wurde hier
    #     self._require().__dict__.get("_registry_stub", _RegistryStub())
    # zurueckgegeben. Da "_registry_stub" NIE gesetzt wurde, lieferte jeder
    # Zugriff eine FRISCHE, leere _RegistryStub-Instanz. Folge:
    #   - registry.register(...) schrieb in ein Wegwerf-Objekt
    #   - registry.get("@e1") las aus einem anderen, leeren Objekt -> None
    #   - len(registry) war immer 0
    # Damit war das komplette @eN-Ref-System (snapshot -> click/type) kaputt.
    # Wir cachen die Registry jetzt EINMAL pro Instanz.
    @property
    def registry(self):
        inst = self._require()
        reg = inst.__dict__.get("_registry_stub")
        if reg is None:
            reg = _RegistryStub()
            inst._registry_stub = reg
        return reg

    def set_active_page(self, page: Page) -> None:
        self._require().set_active_page(page)

    # --- Forwarding fuer alle anderen Methoden ---

    def __getattr__(self, name: str):
        # Private/Dunder-/Marker-Attribute NICHT an _require() weiterleiten.
        # Sonst wirft das Proxy RuntimeError statt AttributeError, sobald Python
        # oder Bibliotheken probehalber nach Sondernamen fragen -- z.B.
        # inspect.iscoroutinefunction -> getattr(obj, "_is_coroutine_marker"),
        # copy/pickle -> "__deepcopy__"/"__reduce_ex__", asyncio -> "__await__".
        # Das bricht den getattr(obj, name, default)- und hasattr()-Vertrag und
        # laesst jede Introspektion abstuerzen, solange noch kein Manager
        # registriert ist (genau das blockierte catalog.discover() und damit den
        # Auto-Start des MCP-Servers). Fuer solche Namen sauber AttributeError
        # signalisieren; nur echte, oeffentliche Methoden werden weitergeleitet.
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._require(), name)

    # --- Eigene async-Methoden als Shortcut ---

    async def start_local(self, **kwargs) -> "BrowserManager":
        if self._instance is None:
            self._instance = BrowserManager(**kwargs)
        return await self._instance.start_local()

    async def connect_cdp(self, endpoint_url: str, **kwargs) -> "BrowserManager":
        if self._instance is None:
            self._instance = BrowserManager(**kwargs)
        return await self._instance.connect_cdp(endpoint_url)

    async def cleanup(self) -> None:
        if self._instance:
            await self._instance.cleanup()

    async def __aenter__(self):
        if self._instance is None:
            self._instance = BrowserManager()
        await self._instance.start_local()
        return self._instance

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()


class _RegistryStub:
    """
    Stub fuer manager.registry aus v1.x.
    Verhindert AttributeError-Crashes in altem Code ohne echte Registry.
    """

    def __init__(self):
        self._store: dict = {}

    def register(self, data: dict) -> str:
        ref_id = f"@e{len(self._store) + 1}"
        self._store[ref_id] = data
        return ref_id

    def get(self, ref_id: str) -> Optional[dict]:
        return self._store.get(ref_id)

    def clear(self) -> None:
        self._store.clear()

    def items(self):
        """(ref_id, data)-Paare in Einfuege-/Snapshot-Reihenfolge."""
        return self._store.items()

    def find_by_text(
        self,
        keyword: str,
        *,
        role: Optional[str] = None,
        exact: bool = False,
    ) -> list:
        """Sucht registrierte Refs anhand ihres Accessible-Name (case-insensitive).

        Loest Issue #4: Agenten mussten bisher den Snapshot-TEXT per Regex
        parsen, um ein ``@eN`` zu finden -- fragil, weil sich das Ausgabeformat
        aendert (Rolle, Anfuehrungszeichen, OOPIF-Praefixe, "(unlabeled)" ...).
        Stattdessen durchsuchen wir hier direkt die strukturierten
        Registry-Eintraege (jeder Eintrag hat ``name``/``role``), die exakt dem
        entsprechen, was ``browser_click`` ohnehin aufloest.

        Args:
            keyword: gesuchter Text (Teilstring-Match, ausser ``exact=True``).
            role: optionaler Rollen-Filter (z.B. "button", "link").
            exact: bei True muss der Name exakt (case-insensitive) passen.

        Returns:
            Liste von ``{"ref", "name", "role"}`` -- nach Match-Qualitaet
            sortiert: exakte Treffer zuerst, dann kuerzeste (spezifischste) Namen.
        """
        if not keyword:
            return []
        needle = keyword.strip().casefold()
        matches = []
        for ref_id, data in self._store.items():
            name = (data.get("name") or "").strip()
            if not name:
                continue
            if role is not None and data.get("role") != role:
                continue
            hay = name.casefold()
            is_exact = hay == needle
            if exact:
                if not is_exact:
                    continue
            elif needle not in hay:
                continue
            matches.append(
                {
                    "ref": ref_id,
                    "name": name,
                    "role": data.get("role"),
                    "_exact": is_exact,
                    "_len": len(name),
                }
            )
        # Exakte Treffer zuerst, dann kuerzester (spezifischster) Name.
        matches.sort(key=lambda m: (not m["_exact"], m["_len"]))
        for m in matches:
            m.pop("_exact", None)
            m.pop("_len", None)
        return matches

    def __len__(self) -> int:
        return len(self._store)


# Das Singleton -- wird von allen v1.x-Tools via
#   from sin_browser_tools.core import manager
#   manager.page  /  manager.connect_cdp()  /  ...
# genutzt.
manager = _ManagerProxy()
