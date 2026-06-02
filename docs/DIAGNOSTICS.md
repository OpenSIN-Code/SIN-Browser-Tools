# Diagnostics & Evidence Layer

> Lueckenlose, CDP-basierte Beweisaufzeichnung fuer SIN-Browser-Tools.
> Ziel: Der Agent stellt **fest** statt zu **vermuten**. Jede Aktion und jedes
> Browser-Ereignis wird mit Zeitstempel, Sequenznummer und Korrelations-ID
> aufgezeichnet.

## Warum

Die eingebaute Observability (`TraceLogger`) hoert nur auf `page.on("response")`
und protokolliert `url/status/method`. Damit fehlen Request-/Response-Bodies,
Console-Logs, JS-Exceptions, Lifecycle-Events, Performance-Metriken und jegliche
Element-/DOM-Details pro Aktion. Der Evidence-Layer schliesst diese Luecke ueber
eine echte `CDPSession`, die **alle** relevanten Domains abonniert.

## Erfasste CDP-Domains

| Domain | Events (Auszug) | Artefakt |
|---|---|---|
| Network | `requestWillBeSent(ExtraInfo)`, `responseReceived(ExtraInfo)`, `dataReceived`, `loadingFinished`, `loadingFailed`, `webSocketFrame*`, `eventSourceMessageReceived` | JSONL + Body-Dateien |
| Runtime | `consoleAPICalled`, `exceptionThrown` (mit Stacktrace) | JSONL |
| Log | `entryAdded` | JSONL |
| Page | `frameNavigated`, `lifecycleEvent`, `javascriptDialogOpening`, `downloadWillBegin`, `fileChooserOpened` | JSONL |
| Performance | `metrics` (gepollt) | JSONL |
| Target | Auto-Attach fuer OOPIFs/Popups | JSONL |
| DOM (pro Aktion) | `backendNodeId`, Box-Model, exakte Klick-Koordinaten, `outerHTML`, computed styles | actions.json + Snapshots |

## Session-Layout

```
<output_dir>/session_<ts>/
  events.jsonl        # globaler Event-Stream (ground truth), je Zeile ein Event
  actions.json        # Action-Trace mit Vorher/Nachher (Screenshot/DOM/Element)
  bodies/<reqid>.*    # Request-/Response-Bodies als Artefakt
  artifacts/*.png     # Screenshots vor/nach jeder Aktion + manuelle Snapshots
  artifacts/*.html    # DOM-Dumps
  artifacts/*.json    # A11y-Snapshots
  report.md           # generierter, menschenlesbarer Report
  report.html         # Report mit eingebetteten Screenshots + Diffs
```

Jede JSONL-Zeile traegt `seq` (global monoton), `t`/`mono` (Zeit) und — sofern
innerhalb einer Aktion erzeugt — `step_id`. Damit ist jede Frage der Form
"was geschah waehrend Klick s0003?" exakt beantwortbar.

## Tools

> Die Signaturen unten entsprechen 1:1 dem Code in
> `sin_browser_tools/tools/diagnostics.py`. Alle Tools geben ein
> MCP-serialisierbares `dict` zurueck.

### `browser_diag_start(base_dir="./.sin_evidence", label="session", network=True, console=True, page=True, performance=True, targets=True, capture_response_bodies=True, capture_request_post_data=True, max_body_bytes=2000000)`
Startet den Recorder und alle CDP-Subscriptions fuer die aktive Page. Einzelne
Domain-Gruppen sind per Flag abschaltbar (spart Volumen). Gibt
`{"status": "started", "session": {...}}` zurueck. Laeuft bereits einer, kommt
`{"status": "already_running", ...}` — vorher `browser_diag_stop()`.

### `browser_diag_action(action, tool, args=None, ref=None)`
Fuehrt ein anderes Browser-Tool aus und umklammert es mit Vorher/Nachher-Beweis:
Screenshot + DOM + A11y-Snapshot + (bei gesetztem `ref`) Element-Details
(backendNodeId, Box-Model, Klick-Koordinaten, outerHTML). `action` ist ein
Freitext-Label (z.B. `"click"`), `tool` der Name des auszufuehrenden Tools
(z.B. `"browser_click"`), `args` dessen Argumente. Gibt `step_id` + Ergebnis zurueck.

```text
browser_diag_action(action="click", tool="browser_click", args={"ref":"@e7"}, ref="@e7")
```

### `browser_diag_snapshot_all(label="manual")`
Erzeugt ad-hoc Screenshot + DOM-Dump + A11y-Snapshot zum aktuellen Zustand und
schreibt einen eigenstaendigen Step-Record. Gibt `step_id` + `state` zurueck.

### `browser_diag_element(ref)`
Loest einen `@eN`-Ref zu echten Element-Beweisen auf (backendNodeId, Box-Model,
Center-Klick-Koordinaten, outerHTML, computed styles).

### `browser_diag_query(domain=None, event=None, step_id=None, contains=None, limit=100)`
Durchsucht `events.jsonl` UND-verknuepft gefiltert. `domain` ∈
`network|console|page|target|performance`, `event` = exakter CDP-Event-Name,
`step_id` = nur Events einer Aktion, `contains` = Substring auf die JSON-Zeile.
Die zentrale Korrelations-Engine.

### `browser_diag_console(level=None, limit=100)`
Console-Logs, JS-Exceptions und Log-Eintraege; `level` ∈ `error|warning|info|log`.

### `browser_diag_network(contains=None, only_failures=False, limit=100)`
Requests/Responses mit Status, Typ, Fehlern und Body-Referenzen. `contains`
filtert per URL-Substring, `only_failures` zeigt nur fehlgeschlagene/blockierte.

### `browser_diag_get_body(request_id)`
Holt den gespeicherten Response-Body zu einer `request_id` (aus
`browser_diag_network`/`browser_diag_query`) als geparstes JSON oder Text.

### `browser_diag_status()`  /  `browser_diag_stop(generate_report_after=True)`
Status + Event-Zaehler des Recorders / Aufzeichnung beenden (schreibt
`actions.json`, optional direkt Report).

### `browser_diag_report(session_dir=None)`
Erzeugt `report.md` + `report.html` mit eingebetteten Screenshots, Timeline,
Netzwerk-/Console-Zusammenfassung und Action-Diffs. Ohne Argument die aktuelle/
zuletzt genutzte Session.

## Typischer Ablauf

```text
browser_diag_start()
browser_diag_action(tool="browser_click", args={"ref":"@e7"}, label="Bestellen")
browser_diag_network(only_failures=True)     # Beleg: schlug ein Request fehl?
browser_diag_console(level="error")          # Beleg: gab es Exceptions?
browser_diag_query(step_id="s0001")          # alles korreliert zu diesem Schritt
browser_diag_stop()
browser_diag_report()                        # report.html als Nachweis
```

## Konfiguration (`EvidenceConfig`)

Definiert in `sin_browser_tools/core/evidence.py`. Alles defaultet auf "maximal".

| Feld | Typ | Default | Bedeutung |
|---|---|---|---|
| `network` | bool | `True` | Network-Domain abonnieren |
| `console` | bool | `True` | Runtime + Log (Console, Exceptions) abonnieren |
| `page` | bool | `True` | Page-Lifecycle/Navigation/Dialoge abonnieren |
| `performance` | bool | `True` | `Performance.metrics` pollen |
| `targets` | bool | `True` | Auto-Attach fuer OOPIFs/Popups |
| `capture_request_post_data` | bool | `True` | POST-Bodies der Requests aufzeichnen |
| `capture_response_bodies` | bool | `True` | Response-Bodies als Artefakte speichern |
| `max_body_bytes` | int | `2_000_000` | Truncation-Grenze pro Body/Payload |
| `body_content_types` | tuple | `(json,text,javascript,xml,html,form-urlencoded,csv)` | nur diese MIME-Substrings als Body speichern (leer == alle) |
| `performance_poll_seconds` | float | `2.0` | Poll-Intervall fuer `Performance.metrics` |
