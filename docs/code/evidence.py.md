# Companion-Doc: `sin_browser_tools/core/evidence.py`

> Begleitdokument zur Quelldatei. Beschreibt Zweck, oeffentliche API,
> Datenformate und Fallstricke. Bei Code-Aenderungen MUSS dieses Dokument
> mitgepflegt werden.

## Zweck

Die Beweis-Engine. Oeffnet eine echte Playwright-`CDPSession`
(`context.new_cdp_session(page)`), abonniert alle relevanten CDP-Domains und
streamt jedes Event als eine JSONL-Zeile. Schliesst die Luecke des eingebauten
`TraceLogger` (der nur `page.on("response")` mit `url/status/method` kennt).

## Oeffentliche API

### `EvidenceConfig` (dataclass)
Schaltet die Erfassung pro Domain + Body-Handling. Felder und Defaults siehe
`docs/DIAGNOSTICS.md` → Konfiguration. Default = maximal.

### `EvidenceRecorder`
| Member | Signatur | Zweck |
|---|---|---|
| `__init__` | `(page, context, base_dir="./.sin_evidence", config=None, session_label="session")` | Legt Session-Ordner + JSONL-Writer an, schreibt `meta.json` |
| `start` | `async () -> EvidenceRecorder` | Aktiviert Domains, bindet Handler, startet Performance-Polling |
| `stop` | `async () -> dict` | Beendet Tasks, deaktiviert Domains, schreibt `actions.json`, gibt `stats()` |
| `begin_step` | `(action, detail=None) -> step_id` | Oeffnet Korrelations-Zeitraum (`step_id`) |
| `end_step` | `(step_id, before, after, error) -> dict` | Schliesst Zeitraum, haengt Vorher/Nachher an |
| `capture_state` | `async (label, step_id, ref=None) -> dict` | Screenshot + DOM + A11y-Snapshot (+ Element bei `ref`) |
| `element_details` | `async (ref) -> dict` | backendNodeId, Box-Model, Klick-Koordinaten, outerHTML, computed styles |
| `note` | `async (label, data=None) -> dict` | Frei definierter Beweis-Record (z.B. Fehlerpfad) |
| `stats` | `() -> dict` | session_id, Pfade, Event-Zaehler |
| `generate_report` | `() -> dict` | delegiert an Modul-`generate_report` |

### Modul-Funktionen
- `record_action(rec, action, ref=None, detail=None)` — async Kontextmanager;
  umklammert eine Aktion mit Vorher/Nachher-Beweis und liefert die `step_id`.
- `generate_report(session_dir)` — baut `report.md` + `report.html` aus den
  JSONL-Rohdaten; gibt `{report_md, report_html, summary}`.

## Datenformate

**JSONL-Zeile (CDP-Event):**
```json
{"seq":42,"kind":"cdp","domain":"network","event":"Network.responseReceived",
 "step_id":"s0003","params":{...},"t":1717000000.12,"mono":12345.6}
```
Weitere `kind`-Werte: `recorder` (started/stopped), `network_body` (Body-Referenz),
`performance` (gepollte Metriken), `note` (frei), `step` (Action-Record).

**`step_id`** korreliert alle Events einer Aktion. **`seq`** ist global monoton.
**`t`** = Wall-Clock (Korrelation mit externen Logs), **`mono`** = monoton (Dauer).

## Fallstricke

- **Response-Bodies sind fluechtig:** `Network.getResponseBody` muss zeitnah nach
  `loadingFinished` laufen; nach einer Navigation verwirft Chromium die Bodies.
  Deshalb wird der Body-Fetch sofort als Task eingeplant (`_on_loading_finished_body`).
- **Grosse Bodies/Payloads** werden bei `max_body_bytes` getrennt: Inhalt als
  Datei nur wenn klein genug, sonst nur Metadaten + `reason`. Truncation wird mit
  `_truncated`-Flags markiert — nie falscher Vollstaendigkeits-Eindruck.
- **`body_content_types`** filtert Binaerformate (Bilder/Fonts) heraus (nur
  Metadaten). Leere Tuple == alles speichern.
- **JSONL ist die Ground Truth**, der Report nur eine Ansicht. Bei Zweifeln immer
  die JSONL auswerten, nicht den Report.
- **Keine Top-Level-Playwright-Imports** — Engine ist isoliert testbar.

## Abhaengigkeiten
`playwright` (CDPSession), Standardbibliothek, optional `structlog`.

## Tests / Verifikation
Writer, Report-Generator, Exception-/Netzwerkfehler-Extraktion, Screenshot-
Einbettung und Body-Truncation sind mit synthetischen CDP-Events ohne laufenden
Browser pruefbar (siehe Engine-Isolation oben).
