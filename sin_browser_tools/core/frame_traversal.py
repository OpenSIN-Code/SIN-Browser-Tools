"""
Unified Frame Traversal Engine.
Scannt ALLE Frames -- OOPIF, Same-Process, Same-Origin, Shadow DOM.
Loest das GMX-OOPIF-Problem architektonisch.

Kernbeobachtung: Playwright's page.frames gibt IMMER alle Frames zurueck,
unabhaengig von Site-Isolation und Process-Boundaries.

Den Accessibility-Tree holen wir pro Frame ueber eine an den Frame gebundene
CDP-Session (Accessibility.getFullAXTree). Hinweis: Eine
``frame.accessibility``-API gibt es in Playwright Python NICHT -- der frueher
hier genutzte Aufruf war ein No-Op, der den AX-Tree immer leer liess.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from playwright.async_api import Frame, Page
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class FrameInfo:
    """Strukturierte Informationen ueber einen Frame."""

    url: str
    name: str
    is_main: bool
    parent_url: Optional[str]
    frame_type: str  # "main", "oopif", "cross-origin-same-process", "same-origin", "unknown"
    ax_tree: Optional[dict] = None
    shadow_roots: list = field(default_factory=list)
    error: Optional[str] = None
    html_length: int = 0
    # Die zugrunde liegende Playwright-Frame-Instanz. Konsumenten (z.B.
    # tools/accessibility.py) brauchen sie, um eine CDP-Session an genau diesen
    # Frame zu binden. NICHT JSON-serialisierbar -- Konsumenten, die FrameInfo
    # serialisieren, muessen dieses Feld auslassen (deep_snapshot baut sein
    # frame_data ohnehin manuell auf).
    frame: Optional[Frame] = None


class UnifiedFrameTraverser:
    """
    Durchsucht ALLE Frames eines Pages -- unabhaengig von Site-Isolation,
    Process-Boundaries oder Shadow DOM Mode.

    Der Schluessel: pro Frame wird eine an den Frame gebundene CDP-Session
    geoeffnet (Accessibility.getFullAXTree). Da die Session am Frame-Target
    haengt, liefert auch ein Cross-Origin-OOPIF seinen eigenen AX-Tree.
    """

    def __init__(self, pierce_shadow: bool = True, include_html: bool = False):
        self.pierce_shadow = pierce_shadow
        self.include_html = include_html

    async def traverse(self, page: Page) -> list[FrameInfo]:
        """
        Haupt-API: Gibt eine vollstaendige Liste aller Frames mit AX-Trees zurueck.
        """
        results: list[FrameInfo] = []

        for frame in page.frames:
            try:
                info = await self._analyze_frame(frame, page)
                results.append(info)
            except Exception as e:
                logger.warning("Frame analysis failed", url=frame.url, error=str(e))
                results.append(
                    FrameInfo(
                        url=frame.url,
                        name=frame.name or "",
                        is_main=frame == page.main_frame,
                        parent_url=frame.parent_frame.url if frame.parent_frame else None,
                        frame_type="error",
                        error=str(e),
                        frame=frame,
                    )
                )

        return results

    async def _cdp_ax_tree(self, frame: Frame, page: Page) -> Optional[dict]:
        """Holt den Accessibility-Tree eines Frames via CDP und baut einen
        verschachtelten Baum (role/name/children) -- OOPIF-sicher.

        Bindet die CDP-Session an den FRAME (nicht die Page), damit auch
        Cross-Origin-OOPIFs ihren eigenen AX-Tree liefern. Faellt bei Fehlern
        sauber auf None zurueck.
        """
        try:
            cdp = await page.context.new_cdp_session(frame)
        except Exception as e:
            logger.debug("CDP session for frame failed", url=frame.url, error=str(e))
            return None
        try:
            await cdp.send("Accessibility.enable")
            result = await cdp.send(
                "Accessibility.getFullAXTree",
                {"pierce": self.pierce_shadow},
            )
            nodes = result.get("nodes", [])
            return self._build_nested_ax_tree(nodes)
        except Exception as e:
            logger.debug("AX getFullAXTree failed", url=frame.url, error=str(e))
            return None
        finally:
            try:
                await cdp.detach()
            except Exception:
                pass

    @staticmethod
    def _build_nested_ax_tree(nodes: list) -> Optional[dict]:
        """Wandelt den flachen CDP-AX-Node-Stream in einen verschachtelten Baum
        mit ``role``/``name``/``children`` um (Form aehnlich der alten
        Playwright-Snapshot-API, damit Downstream-Code unveraendert bleibt).
        """
        if not nodes:
            return None

        by_id: dict[str, dict] = {}
        for n in nodes:
            node_id = n.get("nodeId")
            if node_id is None:
                continue
            by_id[node_id] = {
                "role": (n.get("role") or {}).get("value", "unknown"),
                "name": ((n.get("name") or {}).get("value") or ""),
                "value": (n.get("value") or {}).get("value", ""),
                "_childIds": n.get("childIds", []),
                "_ignored": n.get("ignored", False),
                "children": [],
            }

        # Eltern-Kind-Verknuepfung aufbauen; Wurzel = Knoten ohne Parent.
        child_ids = set()
        for node in by_id.values():
            for cid in node["_childIds"]:
                child = by_id.get(cid)
                if child is not None:
                    node["children"].append(child)
                    child_ids.add(cid)

        roots = [
            node for nid, node in by_id.items() if nid not in child_ids
        ]

        def _clean(node: dict) -> dict:
            node.pop("_childIds", None)
            node.pop("_ignored", None)
            node["children"] = [_clean(c) for c in node["children"]]
            return node

        roots = [_clean(r) for r in roots]
        if not roots:
            return None
        if len(roots) == 1:
            return roots[0]
        return {"role": "RootWebArea", "name": "", "value": "", "children": roots}

    async def _analyze_frame(self, frame: Frame, page: Page) -> FrameInfo:
        """Analysiert einen einzelnen Frame."""
        frame_type = self._detect_frame_type(frame)

        # BUGFIX: Frueher wurde hier 'frame.accessibility.snapshot()' aufgerufen.
        # DIESE API EXISTIERT IN PLAYWRIGHT PYTHON NICHT (weder auf Frame noch
        # auf Page) -- der Aufruf warf immer AttributeError, wurde verschluckt,
        # und ax_tree blieb fuer JEDEN Frame None. Damit war der komplette
        # UnifiedFrameTraverser (und deep_snapshot, das darauf aufbaut) faktisch
        # leer/kaputt.
        #
        # Wir holen den AX-Tree jetzt ueber eine CDP-Session, die an den Frame
        # gebunden ist (OOPIF-sicher), und bauen den flachen Node-Stream in
        # einen verschachtelten Baum um -- aequivalent zur frueheren API-Form.
        ax_tree = await self._cdp_ax_tree(frame, page)

        shadow_roots = []
        if self.pierce_shadow:
            shadow_roots = await self._extract_shadow_dom(frame)

        html_length = 0
        if self.include_html:
            try:
                html_length = await frame.evaluate(
                    "() => document.body?.innerHTML.length || 0"
                )
            except Exception:
                pass

        return FrameInfo(
            url=frame.url,
            name=frame.name or "",
            is_main=frame.parent_frame is None,
            parent_url=frame.parent_frame.url if frame.parent_frame else None,
            frame_type=frame_type,
            ax_tree=ax_tree,
            shadow_roots=shadow_roots,
            html_length=html_length,
            frame=frame,
        )

    @staticmethod
    def _detect_frame_type(frame: Frame) -> str:
        """
        Klassifiziert den Frame-Typ anhand von URL-Origins.
        Wir nutzen bewusst KEINE CDP-Session-Probe mehr -- das war der Fehler
        in der alten Implementierung, der bei GMX's same-process-iframes scheiterte.
        """
        if frame.parent_frame is None:
            return "main"

        parent_origin = UnifiedFrameTraverser._extract_origin(frame.parent_frame.url)
        frame_origin = UnifiedFrameTraverser._extract_origin(frame.url)

        if parent_origin == frame_origin:
            return "same-origin"

        # Heuristik: Wenn die eTLD+1-Domain identisch ist (z.B. gmx.net vs lps.navigator.gmx.net),
        # ist es wahrscheinlich ein Same-Process-Iframe (keine eigene CDP-Session).
        parent_etld1 = UnifiedFrameTraverser._extract_etld1(frame.parent_frame.url)
        frame_etld1 = UnifiedFrameTraverser._extract_etld1(frame.url)

        if parent_etld1 and frame_etld1 and parent_etld1 == frame_etld1:
            return "cross-origin-same-process"

        # Echte Cross-Origin-Cross-Process iframes (OOPIFs)
        return "oopif"

    @staticmethod
    def _extract_origin(url: str) -> str:
        """Extrahiert Origin (scheme + host) aus URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            return url

    @staticmethod
    def _extract_etld1(url: str) -> Optional[str]:
        """Extrahiert eTLD+1 (z.B. 'gmx.net' aus 'lps.navigator.gmx.net')."""
        try:
            from urllib.parse import urlparse
            host = urlparse(url).hostname or ""
            parts = host.split(".")
            if len(parts) >= 2:
                return ".".join(parts[-2:])
        except Exception:
            pass
        return None

    async def _extract_shadow_dom(self, frame: Frame) -> list[dict]:
        """
        Findet alle Shadow Roots im Frame.
        Closed Shadow DOMs koennen nicht direkt gelesen werden, aber wir
        protokollieren das Host-Element fuer Debugging und Ghost-Click-Targeting.
        """
        try:
            return await frame.evaluate("""
                () => {
                    const shadows = [];
                    const walk = (root, depth = 0) => {
                        if (!root || depth > 10) return;
                        const walker = document.createTreeWalker
                            ? document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT)
                            : null;
                        if (!walker) return;

                        let node = walker.currentNode;
                        while (node) {
                            if (node.shadowRoot) {
                                const shadowInfo = {
                                    host_tag: node.tagName.toLowerCase(),
                                    host_id: node.id || null,
                                    host_classes: Array.from(node.classList || []),
                                    mode: node.shadowRoot.mode,
                                    child_count: node.shadowRoot.childElementCount,
                                    depth: depth,
                                    accessible: node.shadowRoot.mode === 'open',
                                    inner_html_length: 0,
                                };
                                if (node.shadowRoot.mode === 'open') {
                                    try {
                                        shadowInfo.inner_html_length =
                                            node.shadowRoot.innerHTML.length;
                                    } catch (e) {}
                                    walk(node.shadowRoot, depth + 1);
                                }
                                shadows.push(shadowInfo);
                            }
                            node = walker.nextNode();
                        }
                    };
                    if (document.body) walk(document.body);
                    return shadows;
                }
            """)
        except Exception as e:
            logger.debug("Shadow DOM extraction failed", error=str(e))
            return []

    async def find_element_across_frames(
        self, page: Page, selector: str
    ) -> Optional[tuple]:
        """
        Sucht ein Element ueber ALLE Frames hinweg.
        Gibt (Frame, ElementHandle) zurueck oder None.
        """
        for frame in page.frames:
            try:
                element = await frame.query_selector(selector)
                if element:
                    return (frame, element)
            except Exception:
                continue
        return None

    def _aggregate_ax_trees(self, frames: list[FrameInfo]) -> dict:
        """Aggregiert alle AX-Trees in einen Root-Node fuer einfache Nutzung."""
        root: dict[str, Any] = {
            "role": "RootWebArea",
            "name": "Aggregated View",
            "children": [],
        }
        for frame_info in frames:
            if frame_info.ax_tree:
                root["children"].append(
                    {
                        "role": "Frame",
                        "name": frame_info.name or frame_info.url,
                        "frame_type": frame_info.frame_type,
                        "children": (
                            [frame_info.ax_tree]
                            if isinstance(frame_info.ax_tree, dict)
                            else []
                        ),
                    }
                )
        return root
