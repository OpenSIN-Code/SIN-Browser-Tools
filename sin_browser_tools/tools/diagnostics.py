"""
Diagnostics-Tools -- macht die lueckenlose CDP-Beweissicherung als ``browser_*``
MCP-Tools verfuegbar.

Diese Tools sind die Antwort auf den Kern-Schmerz: der Agent geht "blind" voran
und trifft ANNAHMEN statt FESTSTELLUNGEN. Mit aktivem Recorder hat jede Aktion
harte Beweise -- CDP-Network (inkl. Bodies), Console, Exceptions, Page-Lifecycle,
Performance, DOM-/Element-Details, Screenshots + Snapshots VOR und NACH.

Workflow fuer den Agenten
-------------------------
1. ``browser_diag_start``                  -> Recorder an, alles wird gestreamt
2. normale Tools nutzen (browser_click, browser_type, browser_navigate, ...)
   oder ``browser_diag_action`` als Wrapper fuer Vorher/Nachher-Beweise
3. ``browser_diag_snapshot_all``           -> Vollerfassung des Ist-Zustands
4. ``browser_diag_query`` / ``browser_diag_console`` / ``browser_diag_network``
   -> gezielt Beweise abfragen statt zu raten
5. ``browser_diag_stop``                   -> Recorder aus + actions.json
6. ``browser_diag_report``                 -> report.md + report.html

Alle Funktionen geben dicts zurueck (MCP-serialisierbar).
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Optional

from sin_browser_tools.core import manager
from sin_browser_tools.core.evidence import (
    EvidenceConfig,
    EvidenceRecorder,
    generate_report,
    record_action,
)

# Aktiver Recorder pro Prozess. Bewusst Singleton: ein Agent fuehrt eine
# zusammenhaengende Untersuchung pro Page-Session.
_recorder: Optional[EvidenceRecorder] = None


def _require_recorder() -> EvidenceRecorder:
    if _recorder is None:
        raise RuntimeError(
            "Kein aktiver EvidenceRecorder. Zuerst browser_diag_start() aufrufen."
        )
    return _recorder


async def browser_diag_start(
    base_dir: str = "./.sin_evidence",
    label: str = "session",
    network: bool = True,
    console: bool = True,
    page: bool = True,
    performance: bool = True,
    targets: bool = True,
    capture_response_bodies: bool = True,
    capture_request_post_data: bool = True,
    max_body_bytes: int = 2000000,
) -> dict:
    """Startet die lueckenlose CDP-Beweissicherung fuer die aktive Page.

    Abonniert die gewuenschten CDP-Domains und streamt jedes Event nach
    ``<base_dir>/<label>_<id>/events.jsonl``. Schalte einzelne Gruppen ab, wenn
    sie gerade nicht gebraucht werden (spart Volumen). Standard ist maximal.
    """
    global _recorder
    if _recorder is not None:
        return {
            "status": "already_running",
            "session": _recorder.stats(),
            "hint": "browser_diag_stop() zuerst aufrufen, um neu zu starten.",
        }
    cfg = EvidenceConfig(
        network=network,
        console=console,
        page=page,
        performance=performance,
        targets=targets,
        capture_response_bodies=capture_response_bodies,
        capture_request_post_data=capture_request_post_data,
        max_body_bytes=max_body_bytes,
    )
    rec = EvidenceRecorder(
        page=manager.page,
        context=manager.context,
        base_dir=base_dir,
        config=cfg,
        session_label=label,
    )
    await rec.start()
    _recorder = rec
    return {"status": "started", "session": rec.stats()}


async def browser_diag_stop(generate_report_after: bool = True) -> dict:
    """Stoppt die Beweissicherung, schreibt actions.json und optional den Report."""
    global _recorder
    rec = _require_recorder()
    stats = await rec.stop()
    report = None
    if generate_report_after:
        with contextlib.suppress(Exception):
            report = rec.generate_report()
    _recorder = None
    return {"status": "stopped", "session": stats, "report": report}


async def browser_diag_status() -> dict:
    """Gibt den aktuellen Recorder-Status + Event-Zaehler zurueck (oder inaktiv)."""
    if _recorder is None:
        return {"active": False}
    return {"active": True, **_recorder.stats()}


async def browser_diag_snapshot_all(label: str = "manual") -> dict:
    """Vollerfassung des Ist-Zustands: Screenshot + DOM-HTML + A11y-Snapshot.

    Erzeugt einen eigenstaendigen Beweis-Schnappschuss (ohne eine Aktion zu
    umschliessen). Nuetzlich vor einer riskanten Entscheidung oder zur
    Dokumentation eines Zwischenzustands.
    """
    rec = _require_recorder()
    step_id = rec.begin_step(f"snapshot:{label}", {"manual": True})
    state = await rec.capture_state(label, step_id, ref=None)
    rec.end_step(step_id, before=state, after=state, error=None)
    return {"status": "captured", "step_id": step_id, "state": state}


async def browser_diag_element(ref: str) -> dict:
    """Loest einen ``@eN``-Ref zu harten DOM-Beweisen auf.

    Liefert backendNodeId, Tag, Attribute, Box-Model, exakte Klick-Koordinaten,
    outerHTML und zentrale computed styles -- der Nachweis, WAS und WO ein
    Element wirklich ist, bevor man darauf klickt.
    """
    rec = _require_recorder()
    return await rec.element_details(ref)


async def browser_diag_action(
    action: str,
    tool: str,
    args: dict = None,
    ref: str = None,
) -> dict:
    """Fuehrt ein anderes ``browser_*``-Tool aus und sichert Vorher/Nachher-Beweise.

    Beispiel (klick auf @e7 mit voller Beweiskette)::

        browser_diag_action(action="click", tool="browser_click",
                            args={"ref": "@e7"}, ref="@e7")

    Vor und nach dem Tool werden Screenshot, DOM, A11y-Snapshot und (bei ``ref``)
    Element-Details festgehalten. Alle in der Zwischenzeit gestreamten CDP-Events
    tragen dieselbe step_id und sind so der Aktion eindeutig zuordenbar.
    """
    from sin_browser_tools.tools import catalog

    rec = _require_recorder()
    args = args or {}
    tools = catalog.discover()
    fn = tools.get(tool)
    if fn is None:
        return {"status": "error", "error": f"unbekanntes Tool: {tool}"}

    result = None
    error = None
    async with record_action(rec, action, ref=ref, detail={"tool": tool, "args": args}) as step_id:
        try:
            result = await fn(**args)
        except Exception as e:  # noqa: BLE001
            error = repr(e)
    return {
        "status": "error" if error else "ok",
        "step_id": step_id,
        "tool": tool,
        "result": _safe(result),
        "error": error,
    }


async def browser_diag_query(
    domain: str = None,
    event: str = None,
    step_id: str = None,
    contains: str = None,
    limit: int = 100,
) -> dict:
    """Durchsucht den aufgezeichneten Event-Stream (events.jsonl) gefiltert.

    So stellt der Agent FEST statt zu RATEN: "Welche Requests gingen waehrend
    Schritt s0003 raus?" / "Gab es eine Exception?" / "Welches Event enthaelt
    'checkout'?".

    Filter (alle optional, UND-verknuepft):
      - ``domain``   : network | console | page | target | performance
      - ``event``    : exakter CDP-Event-Name (z.B. Network.responseReceived)
      - ``step_id``  : nur Events einer bestimmten Aktion
      - ``contains`` : Substring-Match auf die JSON-Zeile
    """
    rec = _require_recorder()
    path = Path(rec.stats()["events_jsonl"])
    return _query_jsonl(path, domain, event, step_id, contains, limit)


async def browser_diag_console(level: str = None, limit: int = 100) -> dict:
    """Gibt console.* Ausgaben, JS-Exceptions und Log-Eintraege zurueck.

    ``level`` filtert optional: error | warning | info | log.
    """
    rec = _require_recorder()
    path = Path(rec.stats()["events_jsonl"])
    out = _query_jsonl(path, domain="console", event=None, step_id=None,
                       contains=None, limit=10000)
    msgs = []
    for ev in out["events"]:
        name = ev.get("event")
        p = ev.get("params", {}) or {}
        if name == "Runtime.consoleAPICalled":
            t = p.get("type", "log")
            msgs.append({"kind": "console", "level": t, "step_id": ev.get("step_id"),
                         "args": p.get("args"), "stack": p.get("stackTrace")})
        elif name == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails", {}) or {}
            msgs.append({"kind": "exception", "level": "error", "step_id": ev.get("step_id"),
                         "text": d.get("text"),
                         "description": (d.get("exception", {}) or {}).get("description")})
        elif name == "Log.entryAdded":
            e = p.get("entry", {}) or {}
            msgs.append({"kind": "log", "level": e.get("level"), "step_id": ev.get("step_id"),
                         "text": e.get("text"), "source": e.get("source")})
    if level:
        msgs = [m for m in msgs if m.get("level") == level]
    return {"count": len(msgs), "messages": msgs[-limit:]}


async def browser_diag_network(contains: str = None, only_failures: bool = False, limit: int = 100) -> dict:
    """Fasst die aufgezeichneten Netzwerk-Requests zusammen (mit Body-Referenzen).

    ``contains`` filtert per URL-Substring, ``only_failures`` zeigt nur
    fehlgeschlagene/blockierte Requests.
    """
    rec = _require_recorder()
    path = Path(rec.stats()["events_jsonl"])
    events = _read_lines(path)
    reqs: dict[str, dict] = {}
    bodies: dict[str, dict] = {}
    for ev in events:
        name = ev.get("event")
        p = ev.get("params", {}) or {}
        if name == "Network.requestWillBeSent":
            r = p.get("request", {}) or {}
            reqs[p.get("requestId")] = {
                "url": r.get("url"), "method": r.get("method"),
                "type": p.get("type"), "step_id": ev.get("step_id"),
                "status": None, "failed": False,
            }
        elif name == "Network.responseReceived":
            rid = p.get("requestId")
            if rid in reqs:
                reqs[rid]["status"] = (p.get("response", {}) or {}).get("status")
        elif name == "Network.loadingFailed":
            rid = p.get("requestId")
            if rid in reqs:
                reqs[rid]["failed"] = True
                reqs[rid]["errorText"] = p.get("errorText")
        elif ev.get("kind") == "network_body":
            bodies[ev.get("request_id")] = {
                "stored": ev.get("stored"), "body_path": ev.get("body_path"),
                "size": ev.get("size"), "reason": ev.get("reason"),
            }
    rows = []
    for rid, r in reqs.items():
        if rid in bodies:
            r["body"] = bodies[rid]
        if only_failures and not r["failed"]:
            continue
        if contains and contains not in (r.get("url") or ""):
            continue
        rows.append(r)
    return {"count": len(rows), "requests": rows[-limit:]}


async def browser_diag_get_body(request_id: str) -> dict:
    """Liefert den gespeicherten Response-Body eines requestId (als Text/JSON).

    request_id stammt aus browser_diag_network()/browser_diag_query().
    """
    rec = _require_recorder()
    base = Path(rec.stats()["session_dir"])
    events = _read_lines(base / "events.jsonl")
    rel = None
    for ev in events:
        if ev.get("kind") == "network_body" and ev.get("request_id") == request_id:
            rel = ev.get("body_path")
            break
    if not rel:
        return {"status": "not_found", "request_id": request_id}
    path = base / rel
    if not path.exists():
        return {"status": "missing_file", "path": str(path)}
    raw = path.read_text(encoding="utf-8", errors="replace")
    parsed = None
    with contextlib.suppress(Exception):
        parsed = json.loads(raw)
    return {"status": "ok", "request_id": request_id, "path": str(path),
            "json": parsed, "text": None if parsed is not None else raw[:20000]}


async def browser_diag_report(session_dir: str = None) -> dict:
    """Generiert report.md + report.html aus den JSONL-Rohdaten.

    Ohne ``session_dir`` wird die aktuell laufende/zuletzt genutzte Session
    verwendet.
    """
    if session_dir:
        return generate_report(session_dir)
    rec = _require_recorder()
    return generate_report(rec.stats()["session_dir"])


# --- interne Helfer --------------------------------------------------------

def _read_lines(path: Path) -> list[dict]:
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


def _query_jsonl(path: Path, domain, event, step_id, contains, limit) -> dict:
    events = _read_lines(path)
    matched = []
    for ev in events:
        if domain and ev.get("domain") != domain:
            continue
        if event and ev.get("event") != event:
            continue
        if step_id and ev.get("step_id") != step_id:
            continue
        if contains and contains not in json.dumps(ev, ensure_ascii=False, default=str):
            continue
        matched.append(ev)
    return {"count": len(matched), "events": matched[-limit:]}


def _safe(obj):
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)
