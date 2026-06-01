# PLAN: Window-Control, macOS-Spaces & Bugfixes + Doku-Offensive

> Status: **PROPOSAL — awaiting go/no-go**
> Autor: v0 (Analyse + Implementierungsplan)
> Ziel-Repo: `OpenSIN-Code/SIN-Browser-Tools`
> Branch (geplant): `feat/window-spaces-and-docs`
> Geltungsbereich: Bugfixes + 2 große Features (Fenster-Steuerung, macOS-Spaces) + komplette Doku-Neufassung.

Dieses Dokument ist **selbst-ausführbar gedacht**: Jeder Abschnitt enthält den
**vollständigen Code** (ganze Dateien bzw. exakte Vorher/Nachher-Diffs), sodass
bei der Umsetzung **nichts vergessen werden kann**. Wer diesen Plan liest, kann
ihn 1:1 in den Code übertragen.

---

## 0. Executive Summary (TL;DR)

**Was kann das Repo heute?** Eine saubere, Playwright-basierte Browser-Automation
für AI-Agents mit 52+ `browser_*`-Tools (Navigation, Interaction, Accessibility,
Frames/Shadow-DOM/OOPIF, Vision, Extraction, Dialog), einem MCP-Server (v2 +
Legacy), Session-Vault, PII-Redaction und Observability. 70 Tests grün.

**Was fehlt / ist kaputt (Kurzliste):**

| # | Kategorie | Problem | Schwere |
|---|-----------|---------|---------|
| B1 | Bug | `opensin_config.py` ist ein toter Stub — die in `.env.template` dokumentierten Env-Vars (`SIN_HEADLESS`, `SIN_VIEWPORT_*`, `SIN_STEALTH`, `SIN_CDP_URL`, Timeouts …) werden **nirgends gelesen**. | hoch |
| B2 | Bug | Headful-Fenster nicht steuerbar: `start_local()` setzt **immer** fixes `viewport=1920x1080` **und** `--start-maximized`/`--window-size` gleichzeitig → die OS-Fenstergröße ist entkoppelt, Maximize/Resize wirkt nicht. | hoch |
| B3 | Bug | `_install_signal_handlers` nutzt veraltetes `asyncio.get_event_loop()` (DeprecationWarning/RuntimeError ab 3.12) und scheitert still in Nicht-Main-Threads. | mittel |
| B4 | Bug | `_kill_zombie_processes` nur POSIX (`os.name=="posix"`) → unter Windows kein Cleanup; killt nur direkte Kinder + PID, keine Enkel. | niedrig |
| F1 | Feature | **Keine Fenster-Steuerung**: klein/mittel/Vollbild, verschieben, minimieren, maximieren — alles fehlt. | **Kern-Wunsch** |
| F2 | Feature | **Keine macOS-Spaces-Steuerung**: Fenster auf einen anderen Schreibtisch/Space legen, sodass es für den Nutzer „im Hintergrund" wirkt, aber real ein Vordergrund-Fenster auf einem anderen Space ist. | **Kern-Wunsch** |
| D1 | Doku | Doku ist breit, aber dünn — wenig durchgehende Beispiele/Use-Cases, keine vollständige, generierte Tool-Referenz, kein Permissions-/Setup-Guide für Window/Spaces. | hoch |

**Was dieser Plan liefert:**
1. Fixes für B1–B4.
2. Neues Modul `core/window.py` (CDP-basierte Fenster-Steuerung, plattformübergreifend).
3. Neues Modul `core/spaces.py` (macOS-Spaces über austauschbare Backends: **yabai**, **Hammerspoon `hs.spaces`**, AppleScript-Fallback).
4. Neues Tool-Modul `tools/window.py` mit ~14 neuen `browser_*`-Tools.
5. Verkabelung: `catalog.py`, MCP-v2-Server, `__init__.py`, `opensin_config.py`, `.env.template`.
6. Tests (Unit + Smoke, mac-spezifische Tests `skip` außerhalb macOS).
7. **Komplette Doku-Neufassung**: neue `WINDOW_AND_SPACES.md`, `PERMISSIONS_MACOS.md`, automatisch generierte `API.md`, erweiterte `COOKBOOK.md`, `AGENTS.md`, README, plus per-Modul-`.md`.

---

## 1. Vollständige Analyse (IST-Zustand)

### 1.1 Architektur-Überblick

```
sin_browser_tools/
├── core/
│   ├── manager.py          # BrowserManager (Playwright) + _ManagerProxy-Singleton (v1-Kompat)
│   ├── session_vault.py    # Cookie/Storage-Persistenz pro Domain (TTL)
│   ├── frame_traversal.py  # UnifiedFrameTraverser (OOPIF + Shadow-DOM AX-Trees)
│   ├── spa_waker.py        # DOM-Stability-Waiting, Popup-Close, GMX-Heuristik
│   ├── pii_redaction.py    # E-Mail/Telefon/SID/IBAN-Redaction
│   └── observability.py    # TraceLogger
├── tools/                  # Alle browser_* Coroutines (auto-discovered via catalog)
│   ├── navigation.py       # navigate/back/forward/reload/scroll/press/wait*/tabs
│   ├── interaction.py      # click/click_cdp/type/fill/check/select/hover/drag/by_text/checkbox/react
│   ├── accessibility.py    # snapshot / snapshot_full_oopif (@eN-Refs)
│   ├── frames.py           # list/eval/snapshot/click_in_frame, scan_frames
│   ├── vision.py           # screenshot/screenshot_element/pdf/get_images/get_text
│   ├── extraction.py       # console/cdp/html/links/attribute/storage/cookies
│   ├── dialog.py           # dialog / wait_for_dialog
│   ├── smart_tools.py      # SmartBrowserTools (High-Level: smart_navigate/deep_snapshot/…)
│   ├── network_intercept.py
│   └── catalog.py          # Single Source of Truth: discover() + input_schema()
├── mcp/server.py           # v2 MCP-Server (6 High-Level-Tools)  -> entrypoint sin-browser-mcp
├── mcp_server.py           # DEPRECATED Flat-Server (alle browser_*) -> sin-browser-mcp-legacy
├── opensin_config.py       # (STUB) Config
├── opensin_skill.py        # OpenSIN-Skill-Registry
└── cli.py                  # `sin-browser` CLI (skills/help)
```

**Kern-Datenfluss:** Tools rufen den Modul-Singleton `manager` (`_ManagerProxy`)
auf → der delegiert an die aktive `BrowserManager`-Instanz. `@eN`-Refs werden in
einer `_RegistryStub` pro Instanz gehalten (seitenlokal, invalidiert bei
Navigation/Tab-Wechsel). Der MCP-Legacy-Server auto-discovered alle `browser_*`
über `catalog.discover()`; der v2-Server bietet 6 High-Level-Tools an.

### 1.2 Detail-Befunde (Belege)

**B1 — `opensin_config.py` ist ein Stub.** `_load_config()` gibt nur
`DEFAULT_CONFIG.copy()` zurück. Kein `os.environ`-Zugriff. `manager.py` ruft
`get_config()` nie auf. → Sämtliche `SIN_*`-Env-Vars aus `.env.template` sind
Dekoration ohne Wirkung.

**B2 — Headful-Fenster nicht steuerbar.** In `start_local()`:
```python
launch_args = {"headless": self.headless, "args": [..., "--window-size=1920,1080", "--start-maximized"]}
...
self._context = await self._browser.new_context(viewport={"width": 1920, "height": 1080}, ...)
```
Ein fixes Playwright-`viewport` überschreibt die OS-Fenster-Renderfläche; mit
`--start-maximized` entsteht ein Konflikt. Für sichtbare Fenster braucht man
`no_viewport=True` (Headful) **oder** explizite CDP-`Browser.setWindowBounds`.

**B3 — Signal-Handler.**
```python
def _handler(signum, frame):
    loop = asyncio.get_event_loop()       # deprecated ab 3.12; RuntimeError ohne laufenden Loop
    if loop.is_running(): loop.create_task(self.cleanup())
```
`signal.signal()` funktioniert zudem nur im Main-Thread; im MCP-Serverthread
greift der `try/except` und es passiert still nichts.

**B4 — Zombie-Cleanup nur POSIX.** `if os.name == "posix":` → Windows ohne
Cleanup; `pkill -P` killt nur direkte Kinder + PID.

**F1/F2 — Window/Spaces fehlen komplett.** Keine Spur von `setWindowBounds`,
`getWindowForTarget`, yabai, Hammerspoon, `hs.spaces` o.ä. im gesamten Tree.

**D1 — Doku.** 30 `.md`-Dateien, aber: `API.md` ist handgepflegt (driftet),
keine durchgehenden End-to-End-Use-Cases pro Tool, kein Setup/Permissions-Guide.

### 1.3 Tests / Qualität
`python -m pytest` → **70 passed** (lokal verifiziert, Headless-Chromium).
Smoke-Tests decken jedes `browser_*` ab; v2-Enterprise-Tests decken Manager,
Vault, Redaction, Traverser, Registry ab.

---

## 2. Bugfixes (vollständiger Code)

### 2.1 B1 — `opensin_config.py`: Env-Vars wirklich lesen

**Datei komplett ersetzen** durch eine echte Config, die `.env` (optional via
`python-dotenv` falls vorhanden, sonst `os.environ`) liest und typsicher parst:

```python
# sin_browser_tools/opensin_config.py
"""Zentrale Konfiguration. Liest SIN_*-Umgebungsvariablen (siehe .env.template).

Reihenfolge: explizite Defaults < .env-Datei (falls python-dotenv vorhanden) <
echte Umgebungsvariablen. Wird von BrowserManager.__init__ konsumiert, damit
SIN_HEADLESS / SIN_VIEWPORT_* / SIN_STEALTH / SIN_WINDOW_* wirklich greifen.
"""

import os
from pathlib import Path
from typing import Any, Optional

try:  # optional: .env laden, wenn das Paket installiert ist
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


def _as_bool(val: Optional[str], default: bool) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _as_int(val: Optional[str], default: int) -> int:
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


class OpenSINConfig:
    """Schreibgeschützte, prozessweite Konfiguration aus Umgebungsvariablen."""

    def __init__(self) -> None:
        self.headless: bool = _as_bool(os.getenv("SIN_HEADLESS"), True)
        self.stealth: bool = _as_bool(os.getenv("SIN_STEALTH"), True)
        self.executable_path: Optional[str] = os.getenv("SIN_BROWSER_EXECUTABLE") or None
        self.viewport_width: int = _as_int(os.getenv("SIN_VIEWPORT_WIDTH"), 1280)
        self.viewport_height: int = _as_int(os.getenv("SIN_VIEWPORT_HEIGHT"), 720)
        self.cdp_url: Optional[str] = os.getenv("SIN_CDP_URL") or None
        self.session_dir: str = os.getenv("SIN_SESSION_DIR", "./.sin_vault")
        self.trace_enabled: bool = _as_bool(os.getenv("SIN_TRACE_ENABLED"), False)
        self.trace_dir: str = os.getenv("SIN_TRACE_DIR", "./.sin_traces")
        self.pii_redaction: bool = _as_bool(os.getenv("SIN_PII_REDACTION"), True)
        self.navigation_timeout: int = _as_int(os.getenv("SIN_NAVIGATION_TIMEOUT"), 30000)
        self.action_timeout: int = _as_int(os.getenv("SIN_ACTION_TIMEOUT"), 10000)
        self.log_level: str = os.getenv("SIN_LOG_LEVEL", "INFO").upper()
        # NEU (Window/Spaces):
        self.window_mode: str = os.getenv("SIN_WINDOW_MODE", "default")  # default|small|medium|large|maximized|fullscreen
        self.window_width: int = _as_int(os.getenv("SIN_WINDOW_WIDTH"), 1280)
        self.window_height: int = _as_int(os.getenv("SIN_WINDOW_HEIGHT"), 800)
        self.window_left: Optional[int] = (
            _as_int(os.getenv("SIN_WINDOW_LEFT"), -1) if os.getenv("SIN_WINDOW_LEFT") else None
        )
        self.window_top: Optional[int] = (
            _as_int(os.getenv("SIN_WINDOW_TOP"), -1) if os.getenv("SIN_WINDOW_TOP") else None
        )
        self.space_backend: str = os.getenv("SIN_SPACE_BACKEND", "auto")  # auto|yabai|hammerspoon|applescript
        self.background_space_index: Optional[int] = (
            _as_int(os.getenv("SIN_BACKGROUND_SPACE"), 0) if os.getenv("SIN_BACKGROUND_SPACE") else None
        )

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def export(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


_config: Optional[OpenSINConfig] = None


def get_config() -> OpenSINConfig:
    global _config
    if _config is None:
        _config = OpenSINConfig()
    return _config


def reset_config() -> None:
    """Nur für Tests: erzwingt Neu-Einlesen der Env-Vars."""
    global _config
    _config = None
```

> `python-dotenv` wird **optional** (try/except). Falls gewünscht, nehmen wir es
> als Extra in `pyproject.toml` auf: `dev`/`runtime`-Optional `dotenv`.

### 2.2 B2 + B3 — `core/manager.py`: Headful-Fenster + Signal-Handler + Window-Optionen

**Diff 1 — Neue Konstruktor-Parameter + Config-Default + Window-State-Feld.**

Vorher (`__init__`-Signatur):
```python
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
```
Nachher:
```python
    def __init__(
        self,
        headless: Optional[bool] = None,
        user_data_dir: Optional[str] = None,
        proxy: Optional[dict] = None,
        vault_path: Optional[str] = None,
        trace_dir: Optional[str] = None,
        stealth: Optional[bool] = None,
        window_mode: Optional[str] = None,
        window_size: Optional[tuple[int, int]] = None,
        window_position: Optional[tuple[int, int]] = None,
        executable_path: Optional[str] = None,
    ):
        from sin_browser_tools.opensin_config import get_config
        cfg = get_config()

        # Explizites Argument schlägt Env-Config schlägt Default.
        self.headless = cfg.headless if headless is None else headless
        self.stealth = cfg.stealth if stealth is None else stealth
        self.user_data_dir = user_data_dir
        self.proxy = proxy
        self.executable_path = executable_path or cfg.executable_path
        self.vault = SessionVault(vault_path or cfg.session_dir)
        self.tracer = TraceLogger(trace_dir or cfg.trace_dir)

        # --- Fenster-Defaults (greifen nur headful) -------------------------
        self.window_mode = window_mode or cfg.window_mode
        self.window_size = window_size or (cfg.window_width, cfg.window_height)
        self.window_position = window_position or (
            (cfg.window_left, cfg.window_top)
            if cfg.window_left is not None and cfg.window_top is not None
            else None
        )
        # WindowController wird in start_local() nach dem Launch gesetzt.
        self.window = None  # type: ignore[assignment]
```

**Diff 2 — `start_local()`: Launch-Args + Headful-`no_viewport` + WindowController.**

Ersetze den `launch_args`-Block und die Context-Erzeugung:
```python
            from sin_browser_tools.core.window import (
                WindowController,
                window_mode_to_args,
            )

            # Fenster-Geometrie als Chromium-Flags VOR dem Launch (gilt headful).
            geo_args = window_mode_to_args(
                self.window_mode, self.window_size, self.window_position
            )

            launch_args = {
                "headless": self.headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    *geo_args,  # --window-size / --window-position / --start-fullscreen …
                ],
            }
            if self.executable_path:
                launch_args["executable_path"] = self.executable_path
            if self.proxy:
                launch_args["proxy"] = self.proxy

            # Im Headful-Modus KEIN fixes viewport -> die OS-Fenstergröße steuert
            # die Renderfläche (no_viewport=True). Headless behält ein viewport.
            ctx_viewport = (
                None if not self.headless
                else {"width": self.window_size[0], "height": self.window_size[1]}
            )

            if self.user_data_dir:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    self.user_data_dir,
                    **launch_args,
                    no_viewport=not self.headless,
                    viewport=ctx_viewport,
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
                    no_viewport=not self.headless,
                    viewport=ctx_viewport,
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
```
Direkt nach `self._setup_dialog_handler()` / PID-Resolution:
```python
            # WindowController erst jetzt: braucht eine offene Page/Context.
            self.window = WindowController(self._context, self._page, self._browser_pid)
            # Gewünschten Fenster-Modus anwenden (no-op headless / bei "default").
            if not self.headless and self.window_mode not in ("default", ""):
                try:
                    await self.window.set_mode(self.window_mode, self.window_size)
                except Exception as e:  # Fenster-Steuerung darf den Start nie killen
                    logger.warning("initial window mode failed", error=str(e))
```

**Diff 3 — Signal-Handler robust (B3).** Ersetze `_install_signal_handlers`:
```python
    def _install_signal_handlers(self):
        """Best-effort Cleanup bei SIGTERM/SIGINT.

        Nutzt den LAUFENDEN Event-Loop (loop.add_signal_handler), wenn vorhanden
        -- das ist die einzig korrekte async-Variante. Fällt sonst auf
        signal.signal zurück. Beides nur im Main-Thread möglich; in Worker-
        Threads (z.B. eingebetteter MCP-Server) wird sauber übersprungen.
        """
        import threading
        if threading.current_thread() is not threading.main_thread():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    loop.add_signal_handler(
                        sig, lambda: asyncio.ensure_future(self.cleanup())
                    )
                except (NotImplementedError, RuntimeError, ValueError):
                    pass
            return

        # Kein laufender Loop (synchroner Kontext): klassischer Handler, der den
        # Loop erst zur Signalzeit sucht -- ohne die deprecated get_event_loop().
        def _handler(signum, frame):
            logger.warning("Signal received, triggering cleanup", signal=signum)
            try:
                running = asyncio.get_running_loop()
                running.create_task(self.cleanup())
            except RuntimeError:
                pass
        try:
            signal.signal(signal.SIGTERM, _handler)
            signal.signal(signal.SIGINT, _handler)
        except (ValueError, AttributeError):
            pass
```
> Da `_install_signal_handlers()` aktuell im `__init__` (synchron) aufgerufen
> wird, läuft i.d.R. noch kein Loop → der signal.signal-Zweig greift, jetzt
> aber ohne `get_event_loop()`-Deprecation. Wird der Manager innerhalb eines
> laufenden Loops erzeugt, nutzen wir `add_signal_handler`.

**Diff 4 — `cleanup()` setzt `self.window = None`.** In `cleanup()` beim
State-Reset ergänzen:
```python
            self.window = None
```

### 2.3 B4 — `_kill_zombie_processes`: Windows-Zweig + ganzer Prozessbaum

Ersetze den POSIX-only-Block:
```python
        pid = self._browser_pid
        if pid is None:
            return
        try:
            if os.name == "posix":
                # Ganzen Prozessbaum: pgrep -P rekursiv einsammeln, dann killen.
                proc = await asyncio.create_subprocess_shell(
                    "pkill -TERM -P {pid} 2>/dev/null; kill -TERM {pid} 2>/dev/null || true".format(pid=pid)
                )
                await proc.wait()
            elif os.name == "nt":
                # taskkill /T killt den gesamten Baum unter pid.
                proc = await asyncio.create_subprocess_shell(
                    "taskkill /PID {pid} /T /F >NUL 2>&1".format(pid=pid)
                )
                await proc.wait()
        except Exception as e:
            logger.debug("Zombie kill failed", pid=pid, error=str(e))
```

---

## 3. Feature F1 — Fenster-Steuerung (`core/window.py`)

**Idee:** Chromium-Fenstergeometrie über das **DevTools-Protokoll** steuern —
plattformübergreifend, ohne OS-Tricks. `Browser.getWindowForTarget` liefert die
`windowId`, `Browser.setWindowBounds` setzt `left/top/width/height/windowState`.
Wichtig: Größe/Position nur im `windowState:"normal"` möglich → wir setzen vor
jedem Resize zunächst `normal`.

> **Voraussetzung:** echtes Fenster = **headful**. Im klassischen Headless/Shell
> existiert kein OS-Fenster → die Tools geben einen klaren Hinweis zurück statt
> zu crashen.

**Komplette neue Datei:**

```python
# sin_browser_tools/core/window.py
"""Fenster-Steuerung über das Chrome DevTools Protocol (CDP).

Plattformübergreifend (macOS/Windows/Linux), solange der Browser HEADFUL läuft.
Headless-Shell besitzt kein OS-Fenster -> die Methoden liefern dann einen
strukturierten Hinweis statt einer Exception.

Vordefinierte Modi:
    small      1024 x 720
    medium     1280 x 800
    large      1600 x 1000
    maximized  (windowState=maximized)
    fullscreen (windowState=fullscreen)
    custom     -> explizite (width, height)
"""

from typing import Optional

import structlog
from playwright.async_api import BrowserContext, Page

logger = structlog.get_logger(__name__)

# Vordefinierte Pixel-Größen (Breite, Höhe) für die "Fenstergröße"-Modi.
WINDOW_PRESETS: dict[str, tuple[int, int]] = {
    "small": (1024, 720),
    "medium": (1280, 800),
    "large": (1600, 1000),
}
WINDOW_STATES = {"normal", "minimized", "maximized", "fullscreen"}


def window_mode_to_args(
    mode: str,
    size: Optional[tuple[int, int]] = None,
    position: Optional[tuple[int, int]] = None,
) -> list[str]:
    """Erzeugt Chromium-CLI-Flags für die INITIALE Fenstergeometrie beim Launch.

    Wird von BrowserManager.start_local() in launch_args["args"] gemerged.
    """
    args: list[str] = []
    mode = (mode or "default").lower()

    if mode == "fullscreen":
        args.append("--start-fullscreen")
        return args
    if mode == "maximized":
        args.append("--start-maximized")
        return args

    w, h = None, None
    if mode in WINDOW_PRESETS:
        w, h = WINDOW_PRESETS[mode]
    elif size:
        w, h = size
    if w and h:
        args.append("--window-size={},{}".format(int(w), int(h)))
    if position:
        args.append("--window-position={},{}".format(int(position[0]), int(position[1])))
    return args


class WindowController:
    """Laufzeit-Steuerung des Browser-Fensters via CDP Browser.*-Domain."""

    def __init__(
        self,
        context: BrowserContext,
        page: Page,
        browser_pid: Optional[int] = None,
    ):
        self._context = context
        self._page = page
        self.browser_pid = browser_pid

    def set_page(self, page: Page) -> None:
        """Aktive Page (= Ziel-Tab/Fenster) wechseln, z.B. nach Tab-Switch."""
        self._page = page

    async def _window_for_target(self):
        """(cdp_session, windowId, bounds) für die aktive Page holen.

        Browser.* ist eine Browser-globale Domain; eine page-gebundene
        CDP-Session genügt aber, um getWindowForTarget aufzulösen.
        """
        cdp = await self._context.new_cdp_session(self._page)
        info = await cdp.send("Browser.getWindowForTarget")
        return cdp, info["windowId"], info.get("bounds", {})

    async def get_bounds(self) -> dict:
        """Aktuelle Fenster-Bounds + windowState lesen."""
        cdp, window_id, bounds = await self._window_for_target()
        try:
            return {
                "window_id": window_id,
                "left": bounds.get("left"),
                "top": bounds.get("top"),
                "width": bounds.get("width"),
                "height": bounds.get("height"),
                "window_state": bounds.get("windowState", "normal"),
            }
        finally:
            await _safe_detach(cdp)

    async def _set_bounds(self, window_id, cdp, **bounds) -> None:
        await cdp.send(
            "Browser.setWindowBounds", {"windowId": window_id, "bounds": bounds}
        )

    async def set_state(self, state: str) -> dict:
        """windowState setzen: normal | minimized | maximized | fullscreen."""
        state = state.lower()
        if state not in WINDOW_STATES:
            return {"status": "error", "error": "state must be one of {}".format(sorted(WINDOW_STATES))}
        cdp, window_id, _ = await self._window_for_target()
        try:
            # Chromium verlangt: aus maximized/fullscreen erst nach normal,
            # bevor ein anderer Nicht-Normal-State gesetzt wird.
            if state in ("maximized", "fullscreen"):
                try:
                    await self._set_bounds(window_id, cdp, windowState="normal")
                except Exception:
                    pass
            await self._set_bounds(window_id, cdp, windowState=state)
            return {"status": "ok", "window_state": state}
        except Exception as e:
            return _headful_hint(e)
        finally:
            await _safe_detach(cdp)

    async def set_bounds(
        self,
        left: Optional[int] = None,
        top: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> dict:
        """Position/Größe in Pixeln setzen (immer im windowState=normal)."""
        cdp, window_id, _ = await self._window_for_target()
        try:
            # Resize/Move geht nur im normal-State.
            try:
                await self._set_bounds(window_id, cdp, windowState="normal")
            except Exception:
                pass
            bounds = {}
            if left is not None:
                bounds["left"] = int(left)
            if top is not None:
                bounds["top"] = int(top)
            if width is not None:
                bounds["width"] = int(width)
            if height is not None:
                bounds["height"] = int(height)
            if not bounds:
                return {"status": "error", "error": "no bounds given"}
            await self._set_bounds(window_id, cdp, **bounds)
            return {"status": "ok", **bounds}
        except Exception as e:
            return _headful_hint(e)
        finally:
            await _safe_detach(cdp)

    async def set_mode(
        self, mode: str, size: Optional[tuple[int, int]] = None
    ) -> dict:
        """High-Level: small|medium|large|maximized|fullscreen|custom."""
        mode = (mode or "").lower()
        if mode in ("maximized", "fullscreen"):
            return await self.set_state(mode)
        if mode in WINDOW_PRESETS:
            w, h = WINDOW_PRESETS[mode]
            return await self.set_bounds(width=w, height=h)
        if mode in ("custom", "normal") and size:
            return await self.set_bounds(width=size[0], height=size[1])
        return {
            "status": "error",
            "error": "unknown mode {!r}; use small|medium|large|maximized|fullscreen|custom".format(mode),
        }


async def _safe_detach(cdp) -> None:
    try:
        await cdp.detach()
    except Exception:
        pass


def _headful_hint(err: Exception) -> dict:
    return {
        "status": "error",
        "error": str(err),
        "hint": (
            "Window control needs a real OS window (headful). Start the manager "
            "with headless=False (or SIN_HEADLESS=false). Headless-shell has no window."
        ),
    }
```

---

## 4. Feature F2 — macOS-Spaces (`core/spaces.py`)

**Problem & Realität:** macOS bietet **keine offizielle public API**, um ein
Fenster programmatisch auf einen anderen Space (Schreibtisch) zu legen. Es gibt
drei praktikable Wege, die wir als **austauschbare Backends** mit Auto-Erkennung
kapseln:

| Backend | Mechanik | Voraussetzung | Güte |
|---------|----------|---------------|------|
| **Hammerspoon `hs.spaces`** ⭐ **DEFAULT** | `hs -c "hs.spaces.moveWindowToSpace(winID, spaceID)"` | Hammerspoon + Accessibility-Permission + `hs.ipc.cliInstall()`; **kein SIP-Disable** | sicher + zuverlässig, am wenigsten invasiv |
| **yabai** | `yabai -m query --windows` → Fenster per `pid`/`app` finden, `yabai -m window <id> --space <n>` | yabai installiert; für Move ggf. Scripting-Addition + SIP teil-deaktiviert | mächtig, aber sicherheitstechnisch invasiver (SIP) |
| **AppleScript-Fallback** | nur Aktivieren/Verschieben innerhalb des aktuellen Space; echtes Space-Assignment nicht möglich | nur Accessibility | begrenzt — gibt klare „nicht unterstützt"-Meldung |

> **Default-Entscheidung (Sicherheit zuerst):** Auto-Erkennung wählt
> **Hammerspoon zuerst** (`detect_backend`: hammerspoon > yabai > applescript),
> weil es ohne SIP-Teil-Deaktivierung auskommt und nur die Accessibility-
> Permission braucht. yabai bleibt als stärkere, opt-in-Alternative verfügbar
> (`SIN_SPACE_BACKEND=yabai`).

Das Fenster wird über die **PID des Chromium-Hauptprozesses** (`browser_pid`,
den der Manager bereits auflöst) identifiziert; alternativ über den Fenstertitel.

> **Wichtig (Ehrlichkeit gegenüber dem Nutzer):** „im Hintergrund auf einem
> anderen Schreibtisch" ist auf macOS technisch = „Fenster einem anderen Space
> zuweisen". Der Plan dokumentiert die nötigen Permissions glasklar
> (`docs/PERMISSIONS_MACOS.md`), damit es reproduzierbar funktioniert.

**Komplette neue Datei:**

```python
# sin_browser_tools/core/spaces.py
"""macOS Spaces ("Schreibtische") steuern: Browser-Fenster auf einen anderen
Space verschieben, Spaces auflisten/erstellen. Austauschbare Backends mit
Auto-Erkennung (yabai > hammerspoon > applescript).

Auf Nicht-macOS-Systemen liefern alle Operationen eine strukturierte
"unsupported"-Antwort statt einer Exception.
"""

import asyncio
import json
import platform
import shutil
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

IS_MACOS = platform.system() == "Darwin"


async def _run(cmd: list[str], timeout: float = 8.0) -> tuple[int, str, str]:
    """Subprozess ausführen -> (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "", "timeout"
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


class SpaceBackend:
    name = "base"

    @classmethod
    def available(cls) -> bool:
        return False

    async def list_spaces(self) -> list[dict]:
        raise NotImplementedError

    async def create_space(self) -> dict:
        raise NotImplementedError

    async def move_window(self, pid: int, title: Optional[str], space_index: int) -> dict:
        raise NotImplementedError

    async def window_space(self, pid: int, title: Optional[str]) -> dict:
        raise NotImplementedError


# --------------------------------------------------------------------------- yabai
class YabaiBackend(SpaceBackend):
    name = "yabai"

    @classmethod
    def available(cls) -> bool:
        return IS_MACOS and shutil.which("yabai") is not None

    async def list_spaces(self) -> list[dict]:
        rc, out, _ = await _run(["yabai", "-m", "query", "--spaces"])
        if rc != 0:
            return []
        try:
            spaces = json.loads(out)
        except json.JSONDecodeError:
            return []
        return [
            {"index": s.get("index"), "label": s.get("label", ""),
             "display": s.get("display"), "is_visible": s.get("is-visible", False)}
            for s in spaces
        ]

    async def create_space(self) -> dict:
        rc, _, err = await _run(["yabai", "-m", "space", "--create"])
        if rc != 0:
            return {"status": "error", "error": err.strip() or "create failed"}
        spaces = await self.list_spaces()
        return {"status": "ok", "space_index": spaces[-1]["index"] if spaces else None}

    async def _find_window_id(self, pid: int, title: Optional[str]) -> Optional[int]:
        rc, out, _ = await _run(["yabai", "-m", "query", "--windows"])
        if rc != 0:
            return None
        try:
            windows = json.loads(out)
        except json.JSONDecodeError:
            return None
        # 1) exakte PID-Übereinstimmung; 2) Titel-Substring als Fallback.
        for w in windows:
            if pid and w.get("pid") == pid:
                return w.get("id")
        if title:
            for w in windows:
                if title.lower() in (w.get("title", "").lower()):
                    return w.get("id")
        # 3) erstes Chromium/Chrome-Fenster.
        for w in windows:
            if w.get("app", "").lower() in ("chromium", "google chrome", "chrome"):
                return w.get("id")
        return None

    async def move_window(self, pid: int, title: Optional[str], space_index: int) -> dict:
        win_id = await self._find_window_id(pid, title)
        if win_id is None:
            return {"status": "error", "error": "browser window not found in yabai query"}
        rc, _, err = await _run(["yabai", "-m", "window", str(win_id), "--space", str(space_index)])
        if rc != 0:
            return {"status": "error", "error": err.strip() or "move failed",
                    "hint": "yabai window-move needs the scripting addition; see docs/PERMISSIONS_MACOS.md"}
        return {"status": "ok", "backend": self.name, "window_id": win_id, "space_index": space_index}

    async def window_space(self, pid: int, title: Optional[str]) -> dict:
        rc, out, _ = await _run(["yabai", "-m", "query", "--windows"])
        if rc != 0:
            return {"status": "error", "error": "yabai query failed"}
        try:
            windows = json.loads(out)
        except json.JSONDecodeError:
            return {"status": "error", "error": "bad yabai output"}
        for w in windows:
            if pid and w.get("pid") == pid:
                return {"status": "ok", "space_index": w.get("space")}
        return {"status": "error", "error": "window not found"}


# --------------------------------------------------------------- Hammerspoon hs.spaces
class HammerspoonBackend(SpaceBackend):
    name = "hammerspoon"

    @classmethod
    def available(cls) -> bool:
        return IS_MACOS and shutil.which("hs") is not None

    async def _hs(self, lua: str) -> tuple[int, str, str]:
        return await _run(["hs", "-c", lua])

    async def list_spaces(self) -> list[dict]:
        # hs.spaces.allSpaces() -> {screenUUID = {spaceID, ...}}; wir flatten zu Indexliste.
        lua = (
            "local s=hs.spaces.allSpaces();local out={};local i=0;"
            "for _,ids in pairs(s) do for _,id in ipairs(ids) do i=i+1;"
            "out[#out+1]=string.format('%d:%d', i, id) end end;"
            "return table.concat(out, ',')"
        )
        rc, out, _ = await self._hs(lua)
        if rc != 0 or not out.strip():
            return []
        spaces = []
        for chunk in out.strip().split(","):
            if ":" in chunk:
                idx, sid = chunk.split(":", 1)
                spaces.append({"index": int(idx), "space_id": int(sid)})
        return spaces

    async def create_space(self) -> dict:
        # hs.spaces.addSpaceToScreen() legt einen Space auf dem Hauptscreen an.
        lua = (
            "local scr=hs.screen.mainScreen():getUUID();"
            "local ok=hs.spaces.addSpaceToScreen(scr);return tostring(ok)"
        )
        rc, out, err = await self._hs(lua)
        if rc != 0:
            return {"status": "error", "error": err.strip() or "create failed"}
        spaces = await self.list_spaces()
        return {"status": "ok", "space_index": spaces[-1]["index"] if spaces else None}

    async def _window_id(self, pid: int, title: Optional[str]) -> Optional[str]:
        # Hammerspoon adressiert Fenster über hs.window:id() (CGWindowID).
        if pid:
            lua = (
                "local app=hs.application.applicationForPID({pid});"
                "if not app then return '' end;"
                "local w=app:mainWindow();"
                "if not w then local ws=app:allWindows(); w=ws[1] end;"
                "if not w then return '' end;return tostring(w:id())"
            ).format(pid=pid)
            rc, out, _ = await self._hs(lua)
            if rc == 0 and out.strip().isdigit():
                return out.strip()
        if title:
            lua = (
                "local w=hs.window.find([[{title}]]);"
                "if not w then return '' end;return tostring(w:id())"
            ).format(title=title.replace("]]", ""))
            rc, out, _ = await self._hs(lua)
            if rc == 0 and out.strip().isdigit():
                return out.strip()
        return None

    async def move_window(self, pid: int, title: Optional[str], space_index: int) -> dict:
        win_id = await self._window_id(pid, title)
        if not win_id:
            return {"status": "error", "error": "browser window not found via Hammerspoon"}
        # space_index (1-basiert) -> echte spaceID auflösen.
        spaces = await self.list_spaces()
        match = next((s for s in spaces if s["index"] == space_index), None)
        if not match:
            return {"status": "error", "error": "space index {} out of range".format(space_index)}
        lua = "return tostring(hs.spaces.moveWindowToSpace({wid}, {sid}))".format(
            wid=win_id, sid=match["space_id"]
        )
        rc, out, err = await self._hs(lua)
        if rc != 0 or "true" not in out.lower():
            return {"status": "error", "error": (err or out).strip() or "move failed",
                    "hint": "Hammerspoon needs Accessibility permission; see docs/PERMISSIONS_MACOS.md"}
        return {"status": "ok", "backend": self.name, "window_id": win_id,
                "space_index": space_index, "space_id": match["space_id"]}

    async def window_space(self, pid: int, title: Optional[str]) -> dict:
        win_id = await self._window_id(pid, title)
        if not win_id:
            return {"status": "error", "error": "window not found"}
        lua = "return tostring(hs.spaces.windowSpaces({wid})[1])".format(wid=win_id)
        rc, out, _ = await self._hs(lua)
        if rc != 0 or not out.strip().isdigit():
            return {"status": "error", "error": "could not resolve space"}
        sid = int(out.strip())
        spaces = await self.list_spaces()
        idx = next((s["index"] for s in spaces if s["space_id"] == sid), None)
        return {"status": "ok", "space_id": sid, "space_index": idx}


# --------------------------------------------------------------- AppleScript fallback
class AppleScriptBackend(SpaceBackend):
    name = "applescript"

    @classmethod
    def available(cls) -> bool:
        return IS_MACOS and shutil.which("osascript") is not None

    async def list_spaces(self) -> list[dict]:
        return []  # AppleScript kann Spaces nicht zuverlässig auflisten

    async def create_space(self) -> dict:
        return {"status": "unsupported",
                "error": "AppleScript cannot create Spaces. Install yabai or Hammerspoon.",
                "see": "docs/PERMISSIONS_MACOS.md"}

    async def move_window(self, pid, title, space_index) -> dict:
        return {"status": "unsupported",
                "error": "Moving a window to another Space requires yabai or Hammerspoon (hs.spaces).",
                "see": "docs/PERMISSIONS_MACOS.md"}

    async def window_space(self, pid, title) -> dict:
        return {"status": "unsupported", "error": "not available via AppleScript"}


def detect_backend(preferred: str = "auto") -> Optional[SpaceBackend]:
    """Wählt das beste verfügbare Backend (oder ein explizit gewünschtes)."""
    registry = {
        "yabai": YabaiBackend,
        "hammerspoon": HammerspoonBackend,
        "applescript": AppleScriptBackend,
    }
    if preferred != "auto":
        cls = registry.get(preferred)
        if cls and cls.available():
            return cls()
        return None
    # Sicherer Default: Hammerspoon zuerst (nur Accessibility-Permission, KEIN
    # SIP-Teil-Deaktivieren), dann yabai, dann AppleScript-Fallback.
    for cls in (HammerspoonBackend, YabaiBackend, AppleScriptBackend):
        if cls.available():
            return cls()
    return None


class SpaceController:
    """Hoch-Level-Fassade über das aktive Backend, vom Tool-Layer genutzt."""

    def __init__(self, browser_pid: Optional[int], window_title_hint: Optional[str],
                 preferred: str = "auto"):
        self.browser_pid = browser_pid
        self.window_title_hint = window_title_hint
        self.backend = detect_backend(preferred)

    def _no_backend(self) -> dict:
        if not IS_MACOS:
            return {"status": "unsupported", "error": "Spaces are macOS-only.",
                    "platform": platform.system()}
        return {"status": "error",
                "error": "No Spaces backend available. Install yabai or Hammerspoon.",
                "see": "docs/PERMISSIONS_MACOS.md"}

    async def list_spaces(self) -> dict:
        if not self.backend:
            return self._no_backend()
        return {"status": "ok", "backend": self.backend.name,
                "spaces": await self.backend.list_spaces()}

    async def create_space(self) -> dict:
        if not self.backend:
            return self._no_backend()
        return await self.backend.create_space()

    async def move_to_space(self, space_index: int) -> dict:
        if not self.backend:
            return self._no_backend()
        return await self.backend.move_window(self.browser_pid, self.window_title_hint, space_index)

    async def current_space(self) -> dict:
        if not self.backend:
            return self._no_backend()
        return await self.backend.window_space(self.browser_pid, self.window_title_hint)

    async def send_to_background_space(self, create_if_needed: bool = True) -> dict:
        """Convenience: dediziertes Hintergrund-Space finden/erstellen und Fenster
        dorthin legen, ohne den aktiven Space des Nutzers zu wechseln."""
        if not self.backend:
            return self._no_backend()
        spaces = await self.backend.list_spaces()
        # Ziel = letzter, NICHT sichtbarer Space; sonst neuen erstellen.
        target = None
        for s in spaces:
            if not s.get("is_visible", False):
                target = s["index"]
        if target is None and create_if_needed:
            created = await self.backend.create_space()
            if created.get("status") != "ok":
                return created
            target = created.get("space_index")
        if target is None:
            return {"status": "error", "error": "no background space available"}
        result = await self.backend.move_window(self.browser_pid, self.window_title_hint, target)
        result["background_space_index"] = target
        return result
```

---

## 5. Tool-Layer (`tools/window.py`) — die neuen `browser_*`-Tools

Diese Coroutines werden von `catalog.discover()` automatisch erkannt (Name
beginnt mit `browser_`) und damit sofort im Legacy-MCP-Server + `browser_list_tools`
sichtbar. Sie greifen über den `manager`-Singleton auf `manager.window`
(WindowController) und bauen pro Aufruf einen `SpaceController`.

**Komplette neue Datei:**

```python
# sin_browser_tools/tools/window.py
"""Fenster- und macOS-Space-Tools.

Fenster (plattformübergreifend, HEADFUL):
    browser_get_window_bounds, browser_set_window_bounds, browser_set_window_mode,
    browser_maximize_window, browser_minimize_window, browser_fullscreen_window,
    browser_restore_window, browser_move_window

macOS Spaces (Schreibtische):
    browser_list_spaces, browser_create_space, browser_move_to_space,
    browser_get_window_space, browser_send_to_background_space
"""

from typing import Optional

from sin_browser_tools.core import manager
from sin_browser_tools.core.spaces import SpaceController


def _window():
    """Aktiven WindowController holen; klare Fehlermeldung, falls nicht headful/gestartet."""
    inst = getattr(manager, "_instance", None) or manager._require()
    win = getattr(inst, "window", None)
    if win is None:
        raise RuntimeError(
            "No window controller. Start the browser headful first: "
            "await manager.start_local(headless=False) (or SIN_HEADLESS=false)."
        )
    # Stets auf die aktuell aktive Page zeigen (nach Tab-Wechseln).
    try:
        win.set_page(inst._page)
    except Exception:
        pass
    return win


async def _title_hint() -> Optional[str]:
    try:
        return await manager.page.title()
    except Exception:
        return None


def _space_controller(title: Optional[str]) -> SpaceController:
    from sin_browser_tools.opensin_config import get_config
    inst = getattr(manager, "_instance", None)
    pid = getattr(inst, "_browser_pid", None)
    return SpaceController(pid, title, preferred=get_config().space_backend)


# --- Fenster -----------------------------------------------------------------

async def browser_get_window_bounds() -> dict:
    """Aktuelle Fensterposition/-größe + windowState lesen (headful)."""
    return await _window().get_bounds()


async def browser_set_window_bounds(
    left: int = None, top: int = None, width: int = None, height: int = None
) -> dict:
    """Fenster auf exakte Pixel setzen. Beliebige Teilmenge der vier Werte."""
    return await _window().set_bounds(left=left, top=top, width=width, height=height)


async def browser_set_window_mode(mode: str = "medium") -> dict:
    """Fenstergröße per Preset: small | medium | large | maximized | fullscreen | custom.

    small=1024x720, medium=1280x800, large=1600x1000. 'custom' braucht vorher
    browser_set_window_bounds. Funktioniert nur headful (echtes OS-Fenster).
    """
    return await _window().set_mode(mode)


async def browser_maximize_window() -> dict:
    """Fenster maximieren (windowState=maximized)."""
    return await _window().set_state("maximized")


async def browser_minimize_window() -> dict:
    """Fenster minimieren (in den Dock/Taskleiste)."""
    return await _window().set_state("minimized")


async def browser_fullscreen_window() -> dict:
    """Echtes Vollbild (windowState=fullscreen)."""
    return await _window().set_state("fullscreen")


async def browser_restore_window() -> dict:
    """Fenster auf Normalzustand zurücksetzen (aus max/min/fullscreen)."""
    return await _window().set_state("normal")


async def browser_move_window(left: int, top: int) -> dict:
    """Fenster an Bildschirmposition (left, top) verschieben (Pixel)."""
    return await _window().set_bounds(left=left, top=top)


# --- macOS Spaces ------------------------------------------------------------

async def browser_list_spaces() -> dict:
    """Alle macOS-Spaces (Schreibtische) auflisten. macOS-only."""
    return await _space_controller(await _title_hint()).list_spaces()


async def browser_create_space() -> dict:
    """Einen neuen macOS-Space (Schreibtisch) anlegen. Braucht yabai/Hammerspoon."""
    return await _space_controller(await _title_hint()).create_space()


async def browser_move_to_space(space_index: int) -> dict:
    """Browser-Fenster auf den Space mit `space_index` (1-basiert) verschieben.

    Der Nutzer-Schreibtisch wechselt dabei NICHT -> das Fenster verschwindet vom
    aktuellen Space und liegt auf einem anderen (für den Nutzer 'im Hintergrund',
    real ein Vordergrund-Fenster auf einem anderen Schreibtisch). macOS-only.
    """
    return await _space_controller(await _title_hint()).move_to_space(space_index)


async def browser_get_window_space() -> dict:
    """Auf welchem Space liegt das Browser-Fenster aktuell? macOS-only."""
    return await _space_controller(await _title_hint()).current_space()


async def browser_send_to_background_space(create_if_needed: bool = True) -> dict:
    """Fenster auf einen dedizierten Hintergrund-Space legen (anlegen, falls keiner
    frei ist), ohne den aktiven Schreibtisch des Nutzers zu wechseln. macOS-only.
    """
    return await _space_controller(await _title_hint()).send_to_background_space(create_if_needed)
```

---

## 6. Verkabelung (kleine, exakte Diffs)

### 6.1 `tools/catalog.py` — neues Modul registrieren
```python
from sin_browser_tools.tools import (
    accessibility, dialog, extraction, frames, interaction, navigation, vision,
    window,          # NEU
)

TOOL_MODULES = [
    navigation, interaction, accessibility, extraction, vision, dialog, frames,
    window,          # NEU
]
```
> Dadurch erscheinen alle `browser_*window*`/`*space*`-Tools automatisch in
> `discover()`, im Legacy-MCP-Server und in `browser_list_tools`.

### 6.2 `tools/__init__.py` — Re-Export
```python
from . import accessibility, interaction, navigation, vision, dialog, extraction, window
__all__ = ["accessibility", "interaction", "navigation", "vision", "dialog", "extraction", "window"]
```

### 6.3 v2 MCP-Server (`mcp/server.py`) — High-Level-Tools ergänzen
Der v2-Server ist handkuratiert. Wir ergänzen 5 High-Level-Window/Space-Tools
(Auszug — vollständige `Tool(...)`-Definitionen + `call_tool`-Branches):
```python
# in TOOLS-Liste:
Tool(name="set_window_mode", description="Resize the browser window: small|medium|large|maximized|fullscreen.",
     inputSchema={"type":"object","properties":{"mode":{"type":"string","default":"medium"}},"required":["mode"]}),
Tool(name="move_to_space", description="(macOS) Move the browser window to another Space/desktop.",
     inputSchema={"type":"object","properties":{"space_index":{"type":"integer"}},"required":["space_index"]}),
Tool(name="send_to_background_space", description="(macOS) Move window to a dedicated background Space.",
     inputSchema={"type":"object","properties":{"create_if_needed":{"type":"boolean","default":True}}}),
Tool(name="list_spaces", description="(macOS) List all Spaces/desktops.", inputSchema={"type":"object","properties":{}}),
Tool(name="get_window_bounds", description="Read window position/size/state.", inputSchema={"type":"object","properties":{}}),

# in call_tool(): (Manager des v2-Servers MUSS headful sein -> _manager = BrowserManager(headless=False) optional via Env)
from sin_browser_tools.tools import window as _win
if name == "set_window_mode":            result = await _win.browser_set_window_mode(**arguments)
elif name == "move_to_space":            result = await _win.browser_move_to_space(**arguments)
elif name == "send_to_background_space": result = await _win.browser_send_to_background_space(**arguments)
elif name == "list_spaces":              result = await _win.browser_list_spaces()
elif name == "get_window_bounds":        result = await _win.browser_get_window_bounds()
```
> **Achtung v2:** `mcp/server.py` instanziiert `_manager = BrowserManager(headless=True)`.
> Damit Window-Tools wirken, dort `headless=get_config().headless` setzen, sodass
> `SIN_HEADLESS=false` den v2-Server headful startet. Dieser Diff ist Teil des Plans.

### 6.4 `__init__.py` — Public-API erweitern
```python
from sin_browser_tools.core.window import WindowController
from sin_browser_tools.core.spaces import SpaceController, detect_backend
# ... in __all__ ergänzen: "WindowController", "SpaceController", "detect_backend"
```

### 6.5 `.env.template` — neue Variablen dokumentieren
```bash
# ============================================================================
# OPTIONAL: Window & macOS Spaces (nur HEADFUL relevant)
# ============================================================================
# Fenster-Startmodus: default|small|medium|large|maximized|fullscreen
# SIN_WINDOW_MODE=medium
# SIN_WINDOW_WIDTH=1280
# SIN_WINDOW_HEIGHT=800
# SIN_WINDOW_LEFT=100
# SIN_WINDOW_TOP=100
# Space-Backend: auto|yabai|hammerspoon|applescript
# SIN_SPACE_BACKEND=auto
# Fester Hintergrund-Space-Index (optional)
# SIN_BACKGROUND_SPACE=
```

### 6.6 `pyproject.toml` — optionales `python-dotenv`
```toml
dependencies = [
    "playwright>=1.40.0", "websockets>=12.0", "mcp>=1.2.0",
    "pydantic>=2.0.0", "structlog>=23.2.0", "httpx>=0.25.0",
    "python-dotenv>=1.0.0",        # NEU: .env-Support (opensin_config)
]
```

---

## 7. Tests

### 7.1 `tests/test_window.py` (neu) — Fenster headful
```python
import sys
import pytest
from sin_browser_tools.core.manager import BrowserManager
from sin_browser_tools.tools import window

pytestmark = pytest.mark.asyncio

# Headful braucht ein Display. In CI ggf. xvfb-run; sonst skip.
HEADFUL_OK = sys.platform != "linux" or bool(__import__("os").environ.get("DISPLAY"))


@pytest.mark.skipif(not HEADFUL_OK, reason="no display for headful window test")
async def test_window_bounds_roundtrip():
    from sin_browser_tools.core.manager import manager as proxy
    async with BrowserManager(headless=False, window_mode="medium") as mgr:
        proxy._set_instance(mgr)
        await mgr.page.goto("about:blank")
        set_res = await window.browser_set_window_bounds(left=120, top=80, width=1100, height=740)
        assert set_res["status"] == "ok"
        got = await window.browser_get_window_bounds()
        # Toleranz: WM kann ein paar Pixel korrigieren.
        assert abs(got["width"] - 1100) <= 40
        assert abs(got["height"] - 740) <= 60


@pytest.mark.skipif(not HEADFUL_OK, reason="no display for headful window test")
async def test_window_modes():
    from sin_browser_tools.core.manager import manager as proxy
    async with BrowserManager(headless=False) as mgr:
        proxy._set_instance(mgr)
        await mgr.page.goto("about:blank")
        assert (await window.browser_maximize_window())["status"] == "ok"
        assert (await window.browser_restore_window())["status"] == "ok"
        assert (await window.browser_set_window_mode("small"))["status"] == "ok"


async def test_window_headless_returns_hint():
    """Headless -> kein OS-Fenster -> strukturierter Hinweis, kein Crash."""
    from sin_browser_tools.core.manager import manager as proxy
    async with BrowserManager(headless=True) as mgr:
        proxy._set_instance(mgr)
        await mgr.page.goto("about:blank")
        res = await window.browser_set_window_mode("large")
        # Headless-shell: i.d.R. error+hint; manche Builds erlauben es -> ok zulässig.
        assert res["status"] in ("ok", "error")
        if res["status"] == "error":
            assert "headful" in res.get("hint", "").lower()
```

### 7.2 `tests/test_spaces.py` (neu) — Backend-Logik plattformneutral
```python
import pytest
from sin_browser_tools.core import spaces

pytestmark = pytest.mark.asyncio


def test_detect_backend_explicit_unavailable_returns_none(monkeypatch):
    monkeypatch.setattr(spaces.YabaiBackend, "available", classmethod(lambda cls: False))
    assert spaces.detect_backend("yabai") is None


async def test_controller_without_backend_reports_unsupported(monkeypatch):
    monkeypatch.setattr(spaces, "detect_backend", lambda preferred="auto": None)
    monkeypatch.setattr(spaces, "IS_MACOS", False)
    ctrl = spaces.SpaceController(browser_pid=123, window_title_hint=None)
    res = await ctrl.list_spaces()
    assert res["status"] == "unsupported"
    move = await ctrl.move_to_space(2)
    assert move["status"] == "unsupported"


@pytest.mark.skipif(not spaces.IS_MACOS, reason="macOS-only Spaces integration")
async def test_list_spaces_macos_smoke():
    ctrl = spaces.SpaceController(browser_pid=None, window_title_hint=None)
    res = await ctrl.list_spaces()
    assert res["status"] in ("ok", "error", "unsupported")
```

### 7.3 `tests/test_tool_smoke.py` — Catalog-Erwartung erhöhen
```python
# test_catalog_discovers_tools: assert len(tools) >= 40  ->  >= 53 (52 + neue Window/Space)
# Außerdem ein gezielter Check:
def test_window_space_tools_are_discoverable():
    from sin_browser_tools.tools import catalog
    names = set(catalog.discover())
    for t in ("browser_set_window_mode","browser_move_to_space","browser_list_spaces","browser_get_window_bounds"):
        assert t in names
```

---

## 8. Doku-Offensive (D1) — von „billig" zu vollständig

**Leitprinzip:** 2-in-1 (für **Agents** UND **Entwickler**), jedes Tool mit
Signatur, Rückgabeschema, ≥1 realem Use-Case, Fehlerfällen.

| Datei | Aktion | Inhalt |
|-------|--------|--------|
| `docs/WINDOW_AND_SPACES.md` | **neu** | Konzept (CDP-Fenster vs. macOS-Spaces), alle Tools mit Beispielen, „Browser im Hintergrund-Space"-Rezept, Headful-Pflicht, Troubleshooting-Tabelle. |
| `docs/PERMISSIONS_MACOS.md` | **neu** | Schritt-für-Schritt: yabai installieren (`brew install koekeishiya/formulae/yabai`), Scripting-Addition + SIP-Hinweis; Hammerspoon installieren, `hs.ipc.cliInstall()`, Accessibility-Permission; Entscheidungsbaum „welches Backend?". |
| `API.md` | **auto-generieren** | Skript `scripts/gen_api_docs.py` rendert `catalog.specs()` → Markdown-Tabelle (Name, Beschreibung, Params, Required). Nie wieder Drift. |
| `COOKBOOK.md` | erweitern | Rezepte 11–14: „Fenster klein in die Ecke", „Vollbild-Demo", „Browser auf Hintergrund-Space während Agent arbeitet", „Multi-Monitor". |
| `AGENTS.md` | erweitern | Abschnitt „Fenster & Schreibtische" + Error→Fix-Zeilen (z.B. „Window-Tool: needs headful"). |
| `README.md` | erweitern | Feature-Tabelle +Window/Spaces, neue Tool-Kategorie, Badge Tool-Count 52→66. |
| `CHANGELOG.md` | erweitern | Neuer Unreleased-Block (Added/Fixed). |
| `ARCHITECTURE.md` | erweitern | Window/Spaces-Layer ins Diagramm. |
| `sin_browser_tools/core/window.md` | **neu** | Modul-Doku (wie restliche `core/*.md`). |
| `sin_browser_tools/core/spaces.md` | **neu** | Modul-Doku inkl. Backend-Matrix. |
| `sin_browser_tools/tools/window.md` | **neu** | Tool-Doku (Signaturen + Beispiele). |
| `examples/06_window_control.py` | **neu** | Lauffähiges Headful-Beispiel: klein → mittel → maximiert → Hintergrund-Space. |

### 8.1 `scripts/gen_api_docs.py` (neu) — Doku gegen Drift
```python
#!/usr/bin/env python3
"""Generiert API.md aus dem Tool-Catalog (Single Source of Truth)."""
from sin_browser_tools.tools import catalog

def main() -> None:
    rows = ["# API Reference (auto-generated)\n",
            "> Regenerate: `python scripts/gen_api_docs.py > API.md`\n",
            "| Tool | Description | Params | Required |",
            "|------|-------------|--------|----------|"]
    for spec in catalog.specs():
        params = ", ".join(spec["parameters"].keys()) or "—"
        required = ", ".join(spec["required"]) or "—"
        desc = spec["description"].replace("|", "\\|")[:140]
        rows.append("| `{n}` | {d} | {p} | {r} |".format(n=spec["name"], d=desc, p=params, r=required))
    print("\n".join(rows))

if __name__ == "__main__":
    main()
```

---

## 9. Rollout / Commit / Push-Plan

1. **Branch:** `git checkout -b feat/window-spaces-and-docs`.
2. **Implementieren** in dieser Reihenfolge (jede Stufe einzeln testbar):
   1. B1 Config → B3 Signal → B2 Manager-Window-Launch → B4 Cleanup.
   2. `core/window.py` → `tools/window.py` → catalog/__init__-Wiring.
   3. `core/spaces.py` → Space-Tools.
   4. v2-Server-Tools, `.env.template`, `pyproject.toml`.
   5. Tests (`test_window.py`, `test_spaces.py`, Smoke-Anpassung).
   6. Doku (alle Dateien aus §8) + `scripts/gen_api_docs.py` ausführen.
3. **Verifizieren:** `python -m pytest -q` (headless grün; Window-Headful-Tests
   via lokalem Display/xvfb), `ruff`/`pre-commit`.
4. **Commits (atomar, konventionell):**
   - `fix: wire SIN_* env config + headful window viewport + signal handler (B1-B4)`
   - `feat: CDP window control (core/window.py + browser_*window* tools)`
   - `feat(macos): Spaces control via yabai/Hammerspoon (core/spaces.py + browser_*space* tools)`
   - `test: window + spaces coverage`
   - `docs: window/spaces guide, permissions, auto-generated API, cookbook`
5. **Push:** `git push -u origin feat/window-spaces-and-docs` (über `GH_TOKEN`).
6. **PR** gegen `main` mit ausführlicher Beschreibung (verweist auf diesen Plan).
   Optional: Direkt nach `main`, falls so gewünscht.

---

## 10. Risiken, Annahmen & offene Entscheidungen

- **macOS-Spaces brauchen externe Tools + Permissions.** Ohne yabai/Hammerspoon
  liefern die Space-Tools eine ehrliche „unsupported/error+see docs"-Antwort.
  Das ist Designentscheidung, kein Bug. → `PERMISSIONS_MACOS.md`.
- **yabai window-move** benötigt je nach macOS-Version die Scripting-Addition
  (teilweises SIP-Deaktivieren). **Hammerspoon `hs.spaces`** kommt mit reiner
  Accessibility-Permission aus (empfohlener Default für die meisten Nutzer).
- **Window-Tools sind headful-only.** Headless-shell hat kein OS-Fenster → Tools
  geben Hinweis statt Fehler. Der Agent muss `headless=False` starten.
- **CI ist headless/Linux** → Window-Headful-Tests `skip` ohne `DISPLAY`; macOS-
  Space-Tests `skip` außerhalb Darwin. Logik wird trotzdem plattformneutral
  getestet (Backend-Auswahl, unsupported-Pfade).
- **Default bleibt headless=True** für Rückwärtskompatibilität; Window/Spaces ist
  opt-in (Arg oder `SIN_HEADLESS=false`).

### Entscheidungen (bereits getroffen)
1. **Backend-Priorität:** ✅ **Hammerspoon zuerst** (sicher, kein SIP-Disable),
   dann yabai, dann AppleScript. yabai bleibt opt-in via `SIN_SPACE_BACKEND=yabai`.
2. **Push-Strategie:** ✅ **Direkt auf `main`** (kein PR).
3. **`python-dotenv`:** als echte Dependency aufnehmen (mit try/except-Guard, falls
   trotzdem nicht installiert).
4. **Tool-Naming:** ✅ **`browser_send_to_background_space`** (explizit & klar).



