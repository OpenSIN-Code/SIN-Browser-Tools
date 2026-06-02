"""
Evidence Recorder -- lueckenlose CDP-Beweissicherung fuer SIN-Browser-Tools.

WARUM DIESES MODUL EXISTIERT
----------------------------
Der bestehende ``core/observability.py``-TraceLogger haengt nur einen
``page.on("response")``-Listener an und protokolliert pro Response lediglich
``url`` / ``status`` / ``method``. Damit fehlen dem Agenten praktisch ALLE
Beweise, die er fuer Feststellungen (statt Annahmen) braucht:

  * Request-Header, POST-Bodies, Initiator, Timing
  * Response-Bodies (JSON/Text), Caching, Fehlercodes, blockierte Requests
  * WebSocket-Frames
  * console.* Ausgaben, JS-Exceptions, Log.entryAdded (Netzwerk-/Security-Logs)
  * Page-Lifecycle: Navigationen, Frame-Events, Dialoge, Downloads
  * Performance-Metriken
  * pro Aktion: welches Element (backendNodeId), Box-Model, Klick-Koordinaten,
    outerHTML, computed styles, DOM + Screenshot + A11y-Snapshot VOR und NACH

Dieses Modul oeffnet eine echte ``CDPSession`` (Playwright
``context.new_cdp_session(page)``), abonniert alle relevanten CDP-Domains und
schreibt JEDES Event als eine Zeile nach ``events.jsonl`` -- mit Wall-Clock-
Zeit, monotoner Zeit, globaler Sequenznummer und einer Korrelations-``step_id``.
Aktionen werden zusaetzlich als Action-Trace mit Vorher/Nachher-Artefakten
festgehalten. Aus den Rohdaten wird ein menschenlesbarer Report generiert.

Die JSONL-Datei ist die GROUND TRUTH. Der Report ist nur eine Ansicht darauf.

Abhaengigkeiten: nur ``playwright`` + Standardbibliothek (``structlog`` optional).
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:  # structlog ist im Projekt vorhanden, aber wir bleiben tolerant.
    import structlog

    logger = structlog.get_logger(__name__)
except Exception:  # pragma: no cover - fallback ohne structlog
    import logging

    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CDP-Domain-Konfiguration
#
# Jede Gruppe ist einzeln abschaltbar. So kann der Agent z.B. nur Network +
# Console aufzeichnen, wenn Performance/DOM gerade nicht interessieren.
# ---------------------------------------------------------------------------

# Events, die wir pro Domain abonnieren. Bewusst explizit (statt Wildcard),
# damit klar dokumentiert ist, WELCHE Beweise erfasst werden.
NETWORK_EVENTS = (
    "Network.requestWillBeSent",
    "Network.requestWillBeSentExtraInfo",
    "Network.responseReceived",
    "Network.responseReceivedExtraInfo",
    "Network.dataReceived",
    "Network.loadingFinished",
    "Network.loadingFailed",
    "Network.requestServedFromCache",
    "Network.resourceChangedPriority",
    "Network.webSocketCreated",
    "Network.webSocketClosed",
    "Network.webSocketFrameSent",
    "Network.webSocketFrameReceived",
    "Network.webSocketFrameError",
    "Network.eventSourceMessageReceived",
)

CONSOLE_EVENTS = (
    "Runtime.consoleAPICalled",
    "Runtime.exceptionThrown",
    "Log.entryAdded",
)

PAGE_EVENTS = (
    "Page.frameNavigated",
    "Page.frameStartedLoading",
    "Page.frameStoppedLoading",
    "Page.frameAttached",
    "Page.frameDetached",
    "Page.navigatedWithinDocument",
    "Page.frameRequestedNavigation",
    "Page.loadEventFired",
    "Page.domContentEventFired",
    "Page.lifecycleEvent",
    "Page.windowOpen",
    "Page.javascriptDialogOpening",
    "Page.javascriptDialogClosed",
    "Page.fileChooserOpened",
    "Page.downloadWillBegin",
    "Page.downloadProgress",
)

TARGET_EVENTS = (
    "Target.targetCreated",
    "Target.targetDestroyed",
    "Target.targetInfoChanged",
    "Target.attachedToTarget",
    "Target.detachedFromTarget",
)


def _now() -> dict:
    """Zeitstempel-Bundle: Wall-Clock (UTC-Epoch) + monotone Uhr.

    Wall-Clock zum Korrelieren mit externen Logs, monoton fuer exakte Dauer
    ohne NTP-Spruenge.
    """
    return {"t": time.time(), "mono": time.monotonic()}


@dataclass
class EvidenceConfig:
    """Welche Beweise erfasst werden. Alles defaultet auf 'maximal'."""

    network: bool = True
    console: bool = True
    page: bool = True
    performance: bool = True
    targets: bool = True

    capture_request_post_data: bool = True
    capture_response_bodies: bool = True
    # Bodies groesser als das werden nur als Referenz (Groesse + Hash) erfasst,
    # nicht inline -- schuetzt JSONL vor Multi-MB-Binaerdaten.
    max_body_bytes: int = 2_000_000
    # Nur diese Content-Types werden als Body gespeichert (Substring-Match).
    # Leere Menge == alle. Binaerformate (Bilder/Fonts) standardmaessig nur als
    # Metadaten, da fuer Debugging selten der Byte-Inhalt zaehlt.
    body_content_types: tuple = (
        "json",
        "text",
        "javascript",
        "xml",
        "html",
        "form-urlencoded",
        "csv",
    )
    # Performance.metrics werden zusaetzlich in diesem Intervall gepollt.
    performance_poll_seconds: float = 2.0


@dataclass
class _Step:
    step_id: str
    action: str
    detail: dict
    started: dict
    seq_start: int


class JsonlWriter:
    """Append-only JSONL-Schreiber. Eine Zeile == ein Event/Record.

    Im async-Single-Loop laufen alle CDP-Handler im selben Thread; ein Lock
    schuetzt dennoch gegen verschraenkte Writes aus parallelen Body-Fetch-Tasks.
    """

    def __init__(self, path: Path):
        self.path = path
        self._fh = open(path, "a", encoding="utf-8", buffering=1)
        self._lock = asyncio.Lock()
        self._seq = 0

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    async def write(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False, default=_json_default)
        async with self._lock:
            self._fh.write(line + "\n")

    def write_sync(self, record: dict) -> None:
        """Fuer Sync-Kontexte (z.B. atexit/close)."""
        line = json.dumps(record, ensure_ascii=False, default=_json_default)
        self._fh.write(line + "\n")

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._fh.flush()
        with contextlib.suppress(Exception):
            self._fh.close()


def _json_default(obj: Any) -> str:
    """Letzte Rettung fuer nicht-serialisierbare Objekte."""
    return f"<unserializable:{type(obj).__name__}>"


class EvidenceRecorder:
    """Zeichnet lueckenlos alle CDP-Beweise einer Page-Session auf.

    Lebenszyklus::

        rec = EvidenceRecorder(page, context, base_dir="./.sin_evidence")
        await rec.start()
        ...   # Agent klickt/tippt/navigiert; alles wird gestreamt
        await rec.stop()
        report = rec.generate_report()

    Korrelation: ``begin_step()`` / ``end_step()`` (oder der Kontextmanager
    ``record_action`` weiter unten) markieren einen Aktions-Zeitraum. Alle in
    diesem Zeitraum gestreamten CDP-Events tragen dieselbe ``step_id`` und sind
    so eindeutig der ausloesenden Aktion zuordenbar.
    """

    def __init__(
        self,
        page,
        context,
        base_dir: str = "./.sin_evidence",
        config: Optional[EvidenceConfig] = None,
        session_label: str = "session",
    ):
        self.page = page
        self.context = context
        self.config = config or EvidenceConfig()
        self.session_id = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self.session_dir = Path(base_dir) / f"{session_label}_{self.session_id}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "artifacts").mkdir(exist_ok=True)
        (self.session_dir / "bodies").mkdir(exist_ok=True)

        self.writer = JsonlWriter(self.session_dir / "events.jsonl")
        self._cdp = None  # CDPSession
        self._started = False
        self._current_step: Optional[str] = None
        self._steps: list[_Step] = []
        self._step_records: list[dict] = []
        self._perf_task: Optional[asyncio.Task] = None
        self._body_tasks: set[asyncio.Task] = set()
        # request_id -> kompakte Request-Info (fuer Body-Korrelation/Report)
        self._requests: dict[str, dict] = {}
        self._counters: dict[str, int] = {}

        self._meta = {
            "session_id": self.session_id,
            "label": session_label,
            "started_at": _now(),
            "config": self.config.__dict__,
            "page_url": _safe(lambda: self.page.url),
        }
        (self.session_dir / "meta.json").write_text(
            json.dumps(self._meta, indent=2, default=_json_default), encoding="utf-8"
        )

    # -- Lifecycle ----------------------------------------------------------

    async def start(self) -> "EvidenceRecorder":
        if self._started:
            return self
        self._cdp = await self.context.new_cdp_session(self.page)

        # Domains aktivieren + Events binden.
        if self.config.network:
            await self._cdp.send("Network.enable")
            for ev in NETWORK_EVENTS:
                self._cdp.on(ev, self._make_handler(ev, "network"))
        if self.config.console:
            await self._cdp.send("Runtime.enable")
            await self._cdp.send("Log.enable")
            for ev in CONSOLE_EVENTS:
                self._cdp.on(ev, self._make_handler(ev, "console"))
        if self.config.page:
            await self._cdp.send("Page.enable")
            with contextlib.suppress(Exception):
                await self._cdp.send(
                    "Page.setLifecycleEventsEnabled", {"enabled": True}
                )
            for ev in PAGE_EVENTS:
                self._cdp.on(ev, self._make_handler(ev, "page"))
        if self.config.targets:
            with contextlib.suppress(Exception):
                await self._cdp.send(
                    "Target.setAutoAttach",
                    {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True},
                )
            for ev in TARGET_EVENTS:
                self._cdp.on(ev, self._make_handler(ev, "target"))
        if self.config.performance:
            with contextlib.suppress(Exception):
                await self._cdp.send(
                    "Performance.enable", {"timeDomain": "timeTicks"}
                )
            self._perf_task = asyncio.ensure_future(self._poll_performance())

        # Response-Bodies haengen an Network.loadingFinished -> separater Handler.
        if self.config.network and self.config.capture_response_bodies:
            self._cdp.on("Network.loadingFinished", self._on_loading_finished_body)

        self._started = True
        await self.writer.write(
            {
                "seq": self.writer.next_seq(),
                "kind": "recorder",
                "event": "started",
                "session_id": self.session_id,
                "step_id": None,
                **_now(),
            }
        )
        logger.info("EvidenceRecorder started", session=self.session_id, dir=str(self.session_dir))
        return self

    async def stop(self) -> dict:
        if not self._started:
            return self.stats()
        # Laufende Body-Fetches noch zu Ende bringen (best effort, mit Timeout).
        if self._perf_task:
            self._perf_task.cancel()
            with contextlib.suppress(Exception):
                await self._perf_task
        if self._body_tasks:
            with contextlib.suppress(Exception):
                await asyncio.wait(self._body_tasks, timeout=5)

        for domain in ("Network", "Runtime", "Log", "Page", "Performance"):
            with contextlib.suppress(Exception):
                await self._cdp.send(f"{domain}.disable")
        with contextlib.suppress(Exception):
            await self._cdp.detach()

        await self.writer.write(
            {
                "seq": self.writer.next_seq(),
                "kind": "recorder",
                "event": "stopped",
                "session_id": self.session_id,
                "counters": dict(self._counters),
                "step_id": None,
                **_now(),
            }
        )
        self.writer.close()
        self._started = False

        # Step-Index als eigene Datei (schnelles Lesen ohne JSONL-Scan).
        (self.session_dir / "actions.json").write_text(
            json.dumps(self._step_records, indent=2, default=_json_default),
            encoding="utf-8",
        )
        logger.info("EvidenceRecorder stopped", session=self.session_id, counters=self._counters)
        return self.stats()

    # -- CDP-Event-Handler --------------------------------------------------

    def _make_handler(self, event_name: str, domain: str):
        """Erzeugt einen Closure-Handler, der ein CDP-Event nach JSONL schreibt."""

        def handler(params: dict) -> None:
            self._counters[domain] = self._counters.get(domain, 0) + 1
            record = {
                "seq": self.writer.next_seq(),
                "kind": "cdp",
                "domain": domain,
                "event": event_name,
                "step_id": self._current_step,
                "params": self._trim_params(event_name, params),
                **_now(),
            }
            # Request-Index pflegen fuer Body-Korrelation + Report.
            if event_name == "Network.requestWillBeSent":
                req = params.get("request", {}) or {}
                self._requests[params.get("requestId", "")] = {
                    "url": req.get("url"),
                    "method": req.get("method"),
                    "type": params.get("type"),
                    "step_id": self._current_step,
                }
            elif event_name == "Network.responseReceived":
                rid = params.get("requestId", "")
                if rid in self._requests:
                    resp = params.get("response", {}) or {}
                    self._requests[rid]["status"] = resp.get("status")
                    self._requests[rid]["mimeType"] = resp.get("mimeType")
            # Im Event-Loop synchron schreiben -> ueber ensure_future an Lock.
            asyncio.ensure_future(self.writer.write(record))

        return handler

    def _trim_params(self, event_name: str, params: dict) -> dict:
        """Entfernt/kuerzt sehr grosse Felder, ohne Beweiswert zu verlieren.

        POST-Data kann riesig sein; wir respektieren ``max_body_bytes`` und
        markieren Kuerzungen explizit (``_truncated``), damit nie der falsche
        Eindruck von Vollstaendigkeit entsteht.
        """
        if not isinstance(params, dict):
            return {"_raw": params}
        # POST-Data im Request begrenzen.
        if event_name == "Network.requestWillBeSent":
            if not self.config.capture_request_post_data:
                req = dict(params.get("request", {}) or {})
                req.pop("postData", None)
                params = {**params, "request": req}
            else:
                req = params.get("request", {}) or {}
                pd = req.get("postData")
                if isinstance(pd, str) and len(pd) > self.config.max_body_bytes:
                    req = dict(req)
                    req["postData"] = pd[: self.config.max_body_bytes]
                    req["_postData_truncated"] = True
                    params = {**params, "request": req}
        # WebSocket-Frame-Payloads begrenzen.
        for key in ("response", "request"):
            sub = params.get(key)
            if isinstance(sub, dict):
                payload = sub.get("payloadData")
                if isinstance(payload, str) and len(payload) > self.config.max_body_bytes:
                    sub = dict(sub)
                    sub["payloadData"] = payload[: self.config.max_body_bytes]
                    sub["_payload_truncated"] = True
                    params = {**params, key: sub}
        return params

    def _on_loading_finished_body(self, params: dict) -> None:
        """Plant das Nachladen des Response-Bodies via Network.getResponseBody.

        Muss zeitnah passieren: nach einer Navigation verwirft Chromium die
        Bodies und ``getResponseBody`` schlaegt fehl. Daher als eigener Task
        sofort eingeplant.
        """
        rid = params.get("requestId")
        if not rid:
            return
        task = asyncio.ensure_future(self._fetch_body(rid))
        self._body_tasks.add(task)
        task.add_done_callback(self._body_tasks.discard)

    async def _fetch_body(self, request_id: str) -> None:
        info = self._requests.get(request_id, {})
        mime = (info.get("mimeType") or "").lower()
        # Content-Type-Filter (leere Whitelist == alles erlauben).
        if self.config.body_content_types:
            if mime and not any(ct in mime for ct in self.config.body_content_types):
                await self.writer.write(
                    {
                        "seq": self.writer.next_seq(),
                        "kind": "network_body",
                        "request_id": request_id,
                        "url": info.get("url"),
                        "mimeType": mime,
                        "stored": False,
                        "reason": "content-type not in whitelist",
                        "step_id": info.get("step_id"),
                        **_now(),
                    }
                )
                return
        try:
            res = await self._cdp.send("Network.getResponseBody", {"requestId": request_id})
        except Exception as e:
            await self.writer.write(
                {
                    "seq": self.writer.next_seq(),
                    "kind": "network_body",
                    "request_id": request_id,
                    "url": info.get("url"),
                    "stored": False,
                    "reason": f"getResponseBody failed: {e}",
                    "step_id": info.get("step_id"),
                    **_now(),
                }
            )
            return

        body = res.get("body", "")
        is_b64 = res.get("base64Encoded", False)
        raw = base64.b64decode(body) if is_b64 else body.encode("utf-8", "replace")
        size = len(raw)
        too_big = size > self.config.max_body_bytes

        # Body als eigene Artefakt-Datei ablegen (JSONL bleibt schlank).
        ext = _ext_for_mime(mime)
        body_path = self.session_dir / "bodies" / f"{request_id}{ext}"
        record = {
            "seq": self.writer.next_seq(),
            "kind": "network_body",
            "request_id": request_id,
            "url": info.get("url"),
            "method": info.get("method"),
            "status": info.get("status"),
            "mimeType": mime,
            "size": size,
            "base64Encoded": is_b64,
            "step_id": info.get("step_id"),
            "stored": False,
            **_now(),
        }
        if too_big:
            record["reason"] = f"body {size}B exceeds max_body_bytes"
        else:
            with contextlib.suppress(Exception):
                body_path.write_bytes(raw)
                record["stored"] = True
                record["body_path"] = str(body_path.relative_to(self.session_dir))
        await self.writer.write(record)

    async def _poll_performance(self) -> None:
        """Pollt Performance.metrics in Intervallen (kein Push-Event in CDP)."""
        try:
            while True:
                await asyncio.sleep(self.config.performance_poll_seconds)
                with contextlib.suppress(Exception):
                    res = await self._cdp.send("Performance.getMetrics")
                    metrics = {
                        m["name"]: m["value"] for m in res.get("metrics", [])
                    }
                    self._counters["performance"] = (
                        self._counters.get("performance", 0) + 1
                    )
                    await self.writer.write(
                        {
                            "seq": self.writer.next_seq(),
                            "kind": "performance",
                            "event": "Performance.metrics",
                            "step_id": self._current_step,
                            "metrics": metrics,
                            **_now(),
                        }
                    )
        except asyncio.CancelledError:
            return

    # -- Aktions-Korrelation + DOM/Element-Beweise --------------------------

    def begin_step(self, action: str, detail: Optional[dict] = None) -> str:
        step_id = f"s{len(self._steps) + 1:04d}_{uuid.uuid4().hex[:4]}"
        step = _Step(
            step_id=step_id,
            action=action,
            detail=detail or {},
            started=_now(),
            seq_start=self.writer._seq,
        )
        self._steps.append(step)
        self._current_step = step_id
        return step_id

    def end_step(self, step_id: str, before: dict, after: dict, error: Optional[str]) -> dict:
        step = next((s for s in self._steps if s.step_id == step_id), None)
        record = {
            "kind": "action",
            "step_id": step_id,
            "action": step.action if step else "unknown",
            "detail": step.detail if step else {},
            "started": step.started if step else _now(),
            "ended": _now(),
            "error": error,
            "before": before,
            "after": after,
            "seq_range": [step.seq_start if step else 0, self.writer._seq],
        }
        self._step_records.append(record)
        # Auch in den Event-Stream schreiben (eine Zeile, Artefakte referenziert).
        asyncio.ensure_future(self.writer.write({"seq": self.writer.next_seq(), **record}))
        self._current_step = None
        return record

    async def capture_state(self, label: str, step_id: str, ref: Optional[str] = None) -> dict:
        """Friert den Zustand ein: URL, Titel, Screenshot, DOM-HTML, A11y-Snapshot
        und -- falls ein ``@eN``-Ref angegeben ist -- vollstaendige Element-Details.
        """
        prefix = f"{step_id}_{label}"
        art = self.session_dir / "artifacts"
        state: dict = {"label": label, **_now()}
        state["url"] = _safe(lambda: self.page.url)
        state["title"] = await _safe_async(self.page.title)

        # Screenshot (voll sichtbarer Viewport).
        shot = art / f"{prefix}.png"
        if await _safe_async(lambda: self.page.screenshot(path=str(shot), full_page=False)) is not None:
            state["screenshot"] = str(shot.relative_to(self.session_dir))

        # DOM-HTML-Dump.
        html = await _safe_async(self.page.content)
        if isinstance(html, str):
            dom_path = art / f"{prefix}.html"
            with contextlib.suppress(Exception):
                dom_path.write_text(html, encoding="utf-8")
                state["dom_html"] = str(dom_path.relative_to(self.session_dir))
                state["dom_length"] = len(html)

        # Accessibility-Snapshot (nutzt das vorhandene Tool, falls vorhanden).
        snap = await self._a11y_snapshot()
        if snap is not None:
            snap_path = art / f"{prefix}.snapshot.txt"
            with contextlib.suppress(Exception):
                snap_path.write_text(snap, encoding="utf-8")
                state["snapshot"] = str(snap_path.relative_to(self.session_dir))

        # Element-Details aus dem @eN-Ref.
        if ref:
            state["element"] = await self.element_details(ref)
        return state

    async def _a11y_snapshot(self) -> Optional[str]:
        """Holt den A11y-Snapshot ueber das bestehende accessibility-Tool.

        Bewusst lazy + best effort, damit dieses Modul auch ohne den Rest der
        Tool-Suite importierbar bleibt.
        """
        try:
            from sin_browser_tools.tools import accessibility

            res = await accessibility.browser_snapshot()
            if isinstance(res, dict):
                return res.get("snapshot") or json.dumps(res, default=_json_default)
            return str(res)
        except Exception:
            # Fallback: direkter CDP-AX-Tree.
            try:
                tree = await self._cdp.send("Accessibility.getFullAXTree", {})
                return json.dumps(tree, default=_json_default)
            except Exception:
                return None

    async def element_details(self, ref: str) -> dict:
        """Loest einen ``@eN``-Ref zu harten DOM-Beweisen auf.

        Liefert backendNodeId, Tag/Attribute, Box-Model, berechnete
        Klick-Koordinaten (Mittelpunkt des Content-Quads), outerHTML und
        zentrale computed styles. So ist nachweisbar, WO und auf WELCHES
        Element wirklich geklickt wurde -- keine Annahme.
        """
        out: dict = {"ref": ref}
        try:
            from sin_browser_tools.core import manager

            entry = manager.registry.get(ref)
        except Exception as e:
            out["error"] = f"registry lookup failed: {e}"
            return out
        if not entry:
            out["error"] = "ref not found in registry"
            return out

        backend = entry.get("backendDOMNodeId")
        frame = entry.get("frame")
        out["role"] = entry.get("role")
        out["name"] = entry.get("name")
        out["backendDOMNodeId"] = backend

        try:
            cdp = await self.context.new_cdp_session(frame or self.page)
        except Exception as e:
            out["error"] = f"cdp session failed: {e}"
            return out
        try:
            with contextlib.suppress(Exception):
                desc = await cdp.send("DOM.describeNode", {"backendNodeId": backend})
                node = desc.get("node", {})
                out["nodeName"] = node.get("nodeName")
                attrs = node.get("attributes", []) or []
                out["attributes"] = dict(zip(attrs[0::2], attrs[1::2]))

            with contextlib.suppress(Exception):
                box = await cdp.send("DOM.getBoxModel", {"backendNodeId": backend})
                model = box.get("model", {})
                out["box"] = {
                    "width": model.get("width"),
                    "height": model.get("height"),
                    "content": model.get("content"),
                }
                quad = model.get("content")
                if quad and len(quad) >= 8:
                    cx = (quad[0] + quad[2] + quad[4] + quad[6]) / 4
                    cy = (quad[1] + quad[3] + quad[5] + quad[7]) / 4
                    out["click_point"] = {"x": round(cx, 2), "y": round(cy, 2)}

            with contextlib.suppress(Exception):
                html = await cdp.send("DOM.getOuterHTML", {"backendNodeId": backend})
                oh = html.get("outerHTML", "")
                out["outerHTML"] = oh[:4000]
                if len(oh) > 4000:
                    out["outerHTML_truncated"] = True

            with contextlib.suppress(Exception):
                resolved = await cdp.send("DOM.resolveNode", {"backendNodeId": backend})
                obj_id = resolved.get("object", {}).get("objectId")
                if obj_id:
                    styles = await cdp.send(
                        "Runtime.callFunctionOn",
                        {
                            "objectId": obj_id,
                            "returnByValue": True,
                            "functionDeclaration": _COMPUTED_STYLE_FN,
                        },
                    )
                    out["computed_style"] = styles.get("result", {}).get("value")
        finally:
            with contextlib.suppress(Exception):
                await cdp.detach()
        return out

    async def note(self, label: str, data: Optional[dict] = None) -> dict:
        """Schreibt einen frei definierten Beweis-Record in den Event-Stream.

        Gedacht fuer Dinge, die kein CDP-Event sind, aber in der Beweiskette
        nicht fehlen duerfen: ein gefangener Fehler im Flow, eine bewusste
        Entscheidung, ein externer Zustand. So bleibt der Report luckenlos --
        auch der Fehlerpfad ist belegt statt verschluckt.

        Beispiel (Fehlerpfad eines Automatisierungs-Flows)::

            try:
                ...
            except Exception as e:
                await rec.note("flow_error", {"error": repr(e)})
                raise
        """
        record = {
            "seq": self.writer.next_seq(),
            "kind": "note",
            "label": label,
            "data": data or {},
            "step_id": self._current_step,
            **_now(),
        }
        await self.writer.write(record)
        return record

    # -- Helpers ------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "session_id": self.session_id,
            "session_dir": str(self.session_dir),
            "events_jsonl": str(self.session_dir / "events.jsonl"),
            "counters": dict(self._counters),
            "total_events": self.writer._seq,
            "steps": len(self._step_records),
        }

    def generate_report(self) -> dict:
        """Erzeugt report.md + report.html aus den JSONL-Rohdaten."""
        return generate_report(self.session_dir)


# Subset relevanter computed styles -- vollstaendiges getComputedStyle waere
# riesig; diese Auswahl deckt Sichtbarkeit/Klickbarkeit/Layout-Debugging ab.
_COMPUTED_STYLE_FN = """
function() {
  const s = getComputedStyle(this);
  const keep = ['display','visibility','opacity','position','z-index',
    'pointer-events','cursor','width','height','color','background-color',
    'font-size','overflow'];
  const out = {};
  for (const k of keep) out[k] = s.getPropertyValue(k);
  const r = this.getBoundingClientRect();
  out['__rect'] = {x:r.x,y:r.y,w:r.width,h:r.height};
  return out;
}
"""


def _ext_for_mime(mime: str) -> str:
    mime = (mime or "").lower()
    if "json" in mime:
        return ".json"
    if "html" in mime:
        return ".html"
    if "javascript" in mime:
        return ".js"
    if "css" in mime:
        return ".css"
    if "xml" in mime:
        return ".xml"
    if "text" in mime or "csv" in mime:
        return ".txt"
    return ".bin"


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


async def _safe_async(fn):
    try:
        res = fn() if callable(fn) else fn
        if asyncio.iscoroutine(res):
            return await res
        return res
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Action-Trace Kontextmanager
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def record_action(
    recorder: EvidenceRecorder,
    action: str,
    *,
    ref: Optional[str] = None,
    detail: Optional[dict] = None,
):
    """Umschliesst eine Aktion und sichert Vorher/Nachher-Beweise.

    Usage::

        async with record_action(rec, "click", ref="@e7", detail={"text": "Login"}):
            await browser_click("@e7")

    Alle in diesem Block gestreamten CDP-Events tragen dieselbe step_id.
    """
    step_id = recorder.begin_step(action, detail)
    before = await recorder.capture_state("before", step_id, ref)
    error = None
    try:
        yield step_id
    except Exception as e:  # noqa: BLE001 - wir geben den Fehler weiter
        error = repr(e)
        raise
    finally:
        after = await recorder.capture_state("after", step_id, ref)
        recorder.end_step(step_id, before, after, error)


# ---------------------------------------------------------------------------
# Report-Generator (JSONL -> Markdown + HTML)
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            with contextlib.suppress(Exception):
                out.append(json.loads(line))
    return out


def generate_report(session_dir: str | Path) -> dict:
    """Liest events.jsonl + actions.json und schreibt report.md + report.html."""
    session_dir = Path(session_dir)
    events = _read_jsonl(session_dir / "events.jsonl")
    actions = []
    with contextlib.suppress(Exception):
        actions = json.loads((session_dir / "actions.json").read_text(encoding="utf-8"))

    # Aggregationen.
    by_domain: dict[str, int] = {}
    net_requests: list[dict] = []
    console_msgs: list[dict] = []
    exceptions: list[dict] = []
    failures: list[dict] = []
    navigations: list[dict] = []

    for ev in events:
        dom = ev.get("domain")
        if dom:
            by_domain[dom] = by_domain.get(dom, 0) + 1
        name = ev.get("event")
        p = ev.get("params", {}) or {}
        if name == "Network.requestWillBeSent":
            req = p.get("request", {}) or {}
            net_requests.append(
                {
                    "url": req.get("url"),
                    "method": req.get("method"),
                    "type": p.get("type"),
                    "step_id": ev.get("step_id"),
                }
            )
        elif name == "Network.loadingFailed":
            failures.append(
                {
                    "errorText": p.get("errorText"),
                    "blockedReason": p.get("blockedReason"),
                    "canceled": p.get("canceled"),
                    "step_id": ev.get("step_id"),
                }
            )
        elif name == "Runtime.consoleAPICalled":
            console_msgs.append(
                {
                    "type": p.get("type"),
                    "text": _console_text(p.get("args", [])),
                    "step_id": ev.get("step_id"),
                }
            )
        elif name == "Runtime.exceptionThrown":
            det = p.get("exceptionDetails", {}) or {}
            exceptions.append(
                {
                    "text": det.get("text"),
                    "exception": (det.get("exception", {}) or {}).get("description"),
                    "line": det.get("lineNumber"),
                    "url": det.get("url"),
                    "step_id": ev.get("step_id"),
                }
            )
        elif name == "Log.entryAdded":
            entry = p.get("entry", {}) or {}
            if entry.get("level") in ("error", "warning"):
                console_msgs.append(
                    {
                        "type": f"log:{entry.get('level')}",
                        "text": entry.get("text"),
                        "step_id": ev.get("step_id"),
                    }
                )
        elif name == "Page.frameNavigated":
            frame = p.get("frame", {}) or {}
            navigations.append({"url": frame.get("url"), "step_id": ev.get("step_id")})

    md = _render_markdown(
        session_dir, events, actions, by_domain, net_requests,
        console_msgs, exceptions, failures, navigations,
    )
    (session_dir / "report.md").write_text(md, encoding="utf-8")

    html = _render_html(
        session_dir, by_domain, net_requests, console_msgs,
        exceptions, failures, navigations, actions,
    )
    (session_dir / "report.html").write_text(html, encoding="utf-8")

    return {
        "report_md": str(session_dir / "report.md"),
        "report_html": str(session_dir / "report.html"),
        "summary": {
            "total_events": len(events),
            "by_domain": by_domain,
            "network_requests": len(net_requests),
            "console_messages": len(console_msgs),
            "exceptions": len(exceptions),
            "network_failures": len(failures),
            "navigations": len(navigations),
            "actions": len(actions),
        },
    }


def _console_text(args: list) -> str:
    parts = []
    for a in args or []:
        if "value" in a:
            parts.append(str(a.get("value")))
        elif a.get("description"):
            parts.append(str(a.get("description")))
        else:
            parts.append(a.get("type", "?"))
    return " ".join(parts)


def _render_markdown(session_dir, events, actions, by_domain, net, console, exceptions, failures, navs) -> str:
    L = []
    L.append(f"# SIN Evidence Report\n")
    L.append(f"- Session-Verzeichnis: `{session_dir}`")
    L.append(f"- Events gesamt: **{len(events)}**")
    L.append(f"- Aktionen: **{len(actions)}**\n")

    L.append("## Event-Verteilung pro Domain\n")
    for dom, n in sorted(by_domain.items(), key=lambda x: -x[1]):
        L.append(f"- `{dom}`: {n}")
    L.append("")

    if exceptions:
        L.append(f"## JS-Exceptions ({len(exceptions)})\n")
        for e in exceptions[:50]:
            L.append(f"- [{e.get('step_id')}] {e.get('exception') or e.get('text')} ({e.get('url')}:{e.get('line')})")
        L.append("")

    if failures:
        L.append(f"## Netzwerk-Fehler ({len(failures)})\n")
        for f in failures[:50]:
            L.append(f"- [{f.get('step_id')}] {f.get('errorText')} blocked={f.get('blockedReason')}")
        L.append("")

    errs = [c for c in console if "error" in (c.get("type") or "")]
    if errs:
        L.append(f"## Console-Fehler ({len(errs)})\n")
        for c in errs[:50]:
            L.append(f"- [{c.get('step_id')}] {c.get('type')}: {c.get('text')}")
        L.append("")

    if actions:
        L.append(f"## Aktions-Timeline ({len(actions)})\n")
        for a in actions:
            status = "FEHLER" if a.get("error") else "ok"
            L.append(f"### {a.get('step_id')} · {a.get('action')} · {status}")
            if a.get("detail"):
                L.append(f"- Detail: `{json.dumps(a['detail'], ensure_ascii=False)}`")
            el = (a.get("before") or {}).get("element") or (a.get("after") or {}).get("element")
            if el:
                L.append(f"- Element: `{el.get('nodeName')}` {el.get('name')!r} @ {el.get('click_point')}")
            b, af = a.get("before") or {}, a.get("after") or {}
            if b.get("url") != af.get("url"):
                L.append(f"- URL: `{b.get('url')}` -> `{af.get('url')}`")
            for phase, st in (("before", b), ("after", af)):
                if st.get("screenshot"):
                    L.append(f"- {phase} screenshot: `{st['screenshot']}`")
            if a.get("error"):
                L.append(f"- **Error:** {a['error']}")
            L.append("")

    L.append("## Netzwerk-Requests (Auszug)\n")
    for r in net[:100]:
        L.append(f"- {r.get('method')} {r.get('url')} ({r.get('type')})")
    L.append("")
    return "\n".join(L)


def _render_html(session_dir, by_domain, net, console, exceptions, failures, navs, actions) -> str:
    def esc(s):
        return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    rows_actions = ""
    for a in actions:
        b, af = a.get("before") or {}, a.get("after") or {}
        shots = ""
        for phase, st in (("before", b), ("after", af)):
            if st.get("screenshot"):
                shots += f'<figure><figcaption>{phase}</figcaption><img loading="lazy" src="{esc(st["screenshot"])}"></figure>'
        el = b.get("element") or af.get("element") or {}
        status = "err" if a.get("error") else "ok"
        rows_actions += f"""
        <div class="action {status}">
          <h3>{esc(a.get('step_id'))} · {esc(a.get('action'))} · <span class="badge {status}">{'FEHLER' if a.get('error') else 'ok'}</span></h3>
          <div class="meta">
            <div><b>Detail:</b> {esc(json.dumps(a.get('detail', {}), ensure_ascii=False))}</div>
            <div><b>Element:</b> {esc(el.get('nodeName'))} {esc(el.get('name'))} @ {esc(el.get('click_point'))}</div>
            <div><b>URL:</b> {esc(b.get('url'))} → {esc(af.get('url'))}</div>
            {f'<div class="error"><b>Error:</b> {esc(a.get("error"))}</div>' if a.get('error') else ''}
          </div>
          <div class="shots">{shots}</div>
        </div>"""

    def lst(items, fmt):
        return "".join(f"<li>{fmt(i)}</li>" for i in items[:200]) or "<li><i>keine</i></li>"

    dom_rows = "".join(
        f"<tr><td>{esc(d)}</td><td>{n}</td></tr>"
        for d, n in sorted(by_domain.items(), key=lambda x: -x[1])
    )

    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SIN Evidence Report</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; padding: 24px; line-height: 1.5; }}
  h1 {{ margin-top: 0; }}
  section {{ margin-bottom: 32px; }}
  table {{ border-collapse: collapse; }}
  td, th {{ border: 1px solid #8884; padding: 4px 10px; text-align: left; }}
  .action {{ border: 1px solid #8884; border-radius: 8px; padding: 12px 16px; margin: 12px 0; }}
  .action.err {{ border-color: #e5484d; }}
  .badge {{ font-size: 12px; padding: 2px 8px; border-radius: 999px; background: #2e7d32; color: #fff; }}
  .badge.err {{ background: #e5484d; }}
  .meta div {{ font-size: 14px; }}
  .meta .error {{ color: #e5484d; }}
  .shots {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 8px; }}
  figure {{ margin: 0; max-width: 360px; }}
  figure img {{ width: 100%; border: 1px solid #8884; border-radius: 6px; }}
  figcaption {{ font-size: 12px; opacity: .7; }}
  .cols {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; }}
  ul {{ margin: 0; padding-left: 18px; }}
  code, li {{ font-size: 13px; word-break: break-all; }}
</style></head><body>
<h1>SIN Evidence Report</h1>
<p>Session: <code>{esc(session_dir)}</code></p>
<section>
  <h2>Event-Verteilung</h2>
  <table><tr><th>Domain</th><th>Events</th></tr>{dom_rows}</table>
</section>
<section>
  <h2>Aktions-Timeline ({len(actions)})</h2>
  {rows_actions or '<p><i>Keine Aktionen aufgezeichnet.</i></p>'}
</section>
<div class="cols">
  <section><h2>JS-Exceptions ({len(exceptions)})</h2><ul>{lst(exceptions, lambda e: esc((e.get('exception') or e.get('text'))) )}</ul></section>
  <section><h2>Netzwerk-Fehler ({len(failures)})</h2><ul>{lst(failures, lambda f: esc(f.get('errorText')) + ' ' + esc(f.get('blockedReason') or ''))}</ul></section>
  <section><h2>Console ({len(console)})</h2><ul>{lst(console, lambda c: esc(c.get('type')) + ': ' + esc(c.get('text')))}</ul></section>
  <section><h2>Navigationen ({len(navs)})</h2><ul>{lst(navs, lambda n: esc(n.get('url')))}</ul></section>
</div>
<section>
  <h2>Netzwerk-Requests ({len(net)})</h2>
  <ul>{lst(net, lambda r: esc(r.get('method')) + ' ' + esc(r.get('url')))}</ul>
</section>
</body></html>"""
