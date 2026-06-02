# Companion-Doc: `sin_browser_tools/tools/diagnostics.py`

> Begleitdokument zur Quelldatei. Bei Code-Aenderungen mitpflegen.

## Zweck

Macht die Beweis-Engine (`core/evidence.py`) als `browser_diag_*`-MCP-Tools
verfuegbar. Antwort auf den Kern-Schmerz: der Agent geht "blind" voran und trifft
ANNAHMEN statt FESTSTELLUNGEN.

## Auto-Discovery

Wird vom Catalog automatisch entdeckt: jede `async def browser_*`-Funktion in
einem Modul aus `catalog.TOOL_MODULES` ist ein MCP-Tool. Registriert ueber den
Eintrag `"diagnostics"` in `catalog.py` und den Import in `tools/__init__.py`.

## Page-Zugriff

`from sin_browser_tools.core import manager` → `manager.page` / `manager.context`.
Das ist das kanonische Muster (identisch zu `interaction.py`/`accessibility.py`);
`manager` ist ein `_ManagerProxy` mit `page`/`context`/`registry`-Properties.

## Tools (11)

Vollstaendige Signaturen + Semantik: `docs/DIAGNOSTICS.md` → Tools.

| Tool | Kurz |
|---|---|
| `browser_diag_start` | Recorder + CDP-Subscriptions starten |
| `browser_diag_stop` | Beenden, `actions.json`, optional Report |
| `browser_diag_status` | Laeuft er? Event-Zaehler |
| `browser_diag_snapshot_all` | Ad-hoc Screenshot + DOM + A11y |
| `browser_diag_element` | `@eN` → echte DOM-Beweise |
| `browser_diag_action` | Anderes Tool mit Vorher/Nachher-Beweis ausfuehren |
| `browser_diag_query` | `events.jsonl` gefiltert durchsuchen |
| `browser_diag_console` | Console + Exceptions + Logs |
| `browser_diag_network` | Requests/Responses/Fehler + Body-Refs |
| `browser_diag_get_body` | Response-Body zu `request_id` |
| `browser_diag_report` | `report.md` + `report.html` |

## Zustand

- Modul-Singleton `_recorder` (eine Untersuchung pro Page-Session).
- `_require_recorder()` wirft, wenn nicht gestartet — verhindert Bewertungen
  ohne Beweisgrundlage.
- `browser_diag_action` loest das Ziel-Tool ueber `catalog.discover()` auf und
  umklammert es mit `record_action`.

## Fallstricke

- `browser_diag_start` ist idempotent-geschuetzt: laeuft schon einer, kommt
  `already_running` statt eines zweiten Recorders. Erst `stop`.
- Alle Tools geben MCP-serialisierbare `dict`s zurueck; nicht-serialisierbare
  Ergebnisse werden via `_safe()` zu Strings degradiert.
- `request_id` fuer `browser_diag_get_body` stammt aus `browser_diag_network`
  bzw. `browser_diag_query`.

## Querverweise
Laufzeit-Disziplin: Skill `browser-evidence`. Authoring: Skill
`browser-automation`. Engine-Details: `docs/code/evidence.py.md`.
