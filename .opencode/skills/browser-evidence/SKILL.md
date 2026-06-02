---
name: browser-evidence
description: >-
  Erzwingt evidenzbasiertes Arbeiten mit SIN-Browser-Tools. Verwende diese Skill
  IMMER, sobald der Agent einen Browser steuert (klickt, tippt, navigiert,
  Formulare absendet, etwas speichert) oder ein Verhalten/einen Bug
  untersucht. Sie verbietet Annahmen und verlangt fuer jede Aussage einen
  nachweisbaren CDP-Beleg (Network, Console, Exceptions, DOM, Screenshot,
  Snapshot).
---

# Browser Evidence — Forcing Function

## Grundgesetz

> **Keine Behauptung ohne Beleg. Keine Schlussfolgerung ohne Daten.**

Du arbeitest wie ein Wissenschaftler, nicht wie ein Glaubender. Jede Aussage
ueber das Verhalten der Seite MUSS auf einem konkreten, zitierbaren
Evidenz-Artefakt beruhen (eine `seq`/`step_id` aus `events.jsonl`, ein
Screenshot-Pfad, ein Response-Body, eine Exception-Zeile). Formulierungen wie
"wahrscheinlich", "sollte", "vermutlich", "ich nehme an", "normalerweise" sind
bei Tatsachenaussagen ueber die laufende Seite **verboten**. Erlaubt sind nur:
"festgestellt", "belegt durch", "Event #N zeigt", "Screenshot X beweist".

## Pflicht-Lebenszyklus jeder Browser-Session

1. **VOR der ersten Aktion:** `browser_diag_start` aufrufen.
   Ohne aktiven Recorder darfst du KEINE Klick-/Type-/Navigations-Aktion als
   "erfolgreich" oder "fehlgeschlagen" bewerten — dir fehlt der Beweis.

2. **JEDE zustandsaendernde Aktion** (Klick, Eingabe, Submit, Navigation,
   Speichern) wird ueber `browser_diag_action` ausgefuehrt ODER unmittelbar
   davor/danach mit `browser_diag_snapshot_all` umklammert. Damit existiert
   immer ein Vorher/Nachher-Beweis (Screenshot + DOM + A11y-Snapshot +
   Element-Details mit echten Klick-Koordinaten und backendNodeId).

3. **NACH jeder Aktion, bevor du sie bewertest**, ziehst du den Beleg:
   - `browser_diag_query(step_id=...)` → was lief waehrend dieses Schritts?
   - `browser_diag_console(level="error")` → gab es Fehler/Exceptions?
   - `browser_diag_network(only_failures=True)` → gab es fehlgeschlagene Requests?
   Erst dann formulierst du dein Ergebnis — mit Verweis auf die `seq`.

4. **AM ENDE:** `browser_diag_stop` und `browser_diag_report`. Den Pfad zu
   `report.html`/`report.md` nennst du dem Nutzer als pruefbaren Nachweis.

## Bug-Untersuchung (Diagnose-Protokoll)

Wenn ein Problem gemeldet wird, gilt strikt:

1. **Reproduzieren unter Aufzeichnung** — `browser_diag_start`, dann die
   Schritte exakt nachstellen.
2. **Symptom belegen, nicht raten** — den Fehler im Network-/Console-Stream
   lokalisieren (`browser_diag_network(only_failures=True)`,
   `browser_diag_console(level="error")`). Bei HTTP-Fehlern den Body holen:
   `browser_diag_get_body(request_id=...)`.
3. **Ursache aus Daten ableiten** — Korreliere Exception-Zeile, fehlgeschlagenen
   Request und DOM-Zustand ueber dieselbe `step_id`. Die Hypothese MUSS aus den
   Daten folgen, nicht aus Erfahrung.
4. **Fix verifizieren** — nach der Aenderung erneut unter Aufzeichnung
   reproduzieren und beweisen, dass der fehlerhafte Request/die Exception
   verschwunden ist. "Compiliert" oder "sieht gut aus" ist KEIN Nachweis.

## Verbote (harte Regeln)

- NIEMALS ein Aktionsergebnis behaupten, ohne den Recorder laufen zu haben.
- NIEMALS "der Klick hat funktioniert" sagen ohne Vorher/Nachher-Beleg
  (`step_id` mit before/after-Screenshot oder DOM-Diff).
- NIEMALS einen Netzwerk-/Server-Fehler vermuten — immer `browser_diag_network`
  + `browser_diag_get_body` zitieren.
- NIEMALS eine grüne UI als Erfolg werten, wenn `browser_diag_console`
  Exceptions zeigt. Console-Errors schlagen visuelle Eindruecke.
- NIEMALS den Report weglassen, wenn eine nichttriviale Untersuchung lief.

## Tool-Referenz (Kurz)

| Tool | Zweck |
|---|---|
| `browser_diag_start` | Recorder + CDP-Subscriptions starten |
| `browser_diag_action` | Aktion mit Vorher/Nachher-Beweis ausfuehren/umklammern |
| `browser_diag_snapshot_all` | Screenshot + DOM + A11y-Snapshot jetzt |
| `browser_diag_element` | Echte Element-Details (box, Koordinaten, outerHTML) zu `@eN` |
| `browser_diag_query` | Events zu einer `step_id`/`seq`-Spanne abrufen |
| `browser_diag_console` | Console-Logs + Exceptions filtern |
| `browser_diag_network` | Requests/Responses, Fehler, Timing |
| `browser_diag_get_body` | Response-/Request-Body zu einer requestId |
| `browser_diag_status` | Laeuft der Recorder? Welche Session? |
| `browser_diag_stop` | Aufzeichnung beenden |
| `browser_diag_report` | `report.md` + `report.html` mit eingebetteten Belegen |

## Antwort-Stil

Wenn du dem Nutzer ein Ergebnis berichtest, strukturiere es als
**Feststellung → Beleg**:

> "Der Checkout schlaegt fehl. **Beleg:** Event #142 (`step_id=s0007`) zeigt
> `POST /api/checkout` → HTTP 500; Body (`browser_diag_get_body R1`) enthaelt
> `{"error":"inventory_locked"}`; gleichzeitig Exception #145:
> `TypeError: cart is null` in `app.js:42`. Screenshot `s0007_after.png` zeigt
> den haengenden Spinner."

So — und nur so — wird aus Glauben Wissenschaft.
