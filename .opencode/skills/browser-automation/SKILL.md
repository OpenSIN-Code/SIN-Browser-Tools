---
name: browser-automation
description: >-
  Anleitung zum ERSTELLEN von Browser-Automatisierungen mit SIN-Browser-Tools,
  bei denen die lueckenlose CDP-Beweissicherung (Diagnostics/Evidence-Layer) von
  Anfang an fest eingebaut ist. Verwende diese Skill IMMER, wenn du ein neues
  Automatisierungs-Skript, einen Flow, einen Scraper, einen E2E-Ablauf oder ein
  Agenten-Tool schreibst, das einen Browser steuert. Sie sorgt dafuer, dass kein
  Daten-Detail (Network, Console, Exceptions, DOM, Screenshots, Snapshots,
  Performance) verloren geht und nichts ungenutzt liegen bleibt.
---

# Browser Automation — Authoring mit eingebautem Debug-Capture

Diese Skill ist die Bau-Anleitung. Die Schwester-Skill `browser-evidence` ist die
Laufzeit-Forcing-Function (wie man whaerend einer Untersuchung handelt). Hier
geht es darum, **neue** Automatisierungen so zu schreiben, dass Beweissicherung
nicht optional drangeklebt, sondern strukturell unvermeidbar ist.

## Grundprinzip

> **Eine Browser-Automatisierung ohne Evidence-Recorder ist unfertig.**

Jeder Flow, den du erstellst, MUSS:
1. den `EvidenceRecorder` starten, BEVOR die erste Browser-Aktion laeuft,
2. jede zustandsaendernde Aktion ueber `record_action` umklammern,
3. am Ende den Recorder stoppen und einen Report erzeugen,
4. bei Fehlern NICHT still abbrechen, sondern den Fehler ins Evidenz-JSONL
   schreiben (der Report muss den Absturz zeigen).

## Pflicht-Skelett (Python, direkter Engine-Zugriff)

Nutze dieses Geruest fuer eigenstaendige Skripte/Flows. Es ist
copy-paste-fertig und deckt Start/Aktion/Fehler/Stop/Report ab.

```python
import asyncio
from sin_browser_tools.core import manager
from sin_browser_tools.core.evidence import EvidenceRecorder, EvidenceConfig, record_action

async def run_flow():
    # 1) Page sicherstellen (manager kapselt Playwright-Browser/Context/Page).
    #    start_local() ist der reale Entrypoint des BrowserManager-Proxys;
    #    im MCP-/Agentenkontext laeuft die Page bereits -> dann entfaellt dies.
    await manager.start_local()              # nur in standalone-Skripten noetig
    page, context = manager.page, manager.context

    # 2) Recorder starten -> ab hier wird ALLES gestreamt
    rec = EvidenceRecorder(
        page, context,
        base_dir="./.sin_evidence",
        config=EvidenceConfig(),             # Default = maximal
        session_label="checkout_flow",
    )
    await rec.start()

    try:
        # 3) Navigation als Aktion mit Vorher/Nachher-Beweis
        async with record_action(rec, "navigate", detail={"url": "https://shop.example"}):
            await page.goto("https://shop.example")

        # 4) Klick mit echtem Element-Beweis (ref aus Snapshot -> @eN)
        async with record_action(rec, "click", ref="@e7", detail={"what": "Bestellen"}):
            await page.click("text=Bestellen")

        # 5) Nach jeder kritischen Aktion Belege ziehen statt zu raten
        #    (im Skript direkt aus der JSONL lesen, siehe report/query-Helfer)

    except Exception as e:
        # 6) Fehler MUSS in die Evidenz, nicht nur in den Stacktrace
        await rec.note("flow_error", {"error": repr(e)})
        raise
    finally:
        # 7) Immer stoppen + Report — auch bei Absturz
        await rec.stop()
        print(rec.generate_report())         # -> report.md + report.html

asyncio.run(run_flow())
```

## Pflicht-Skelett (Agenten-Tool ueber MCP)

Wenn der Flow vom Agenten ueber die `browser_diag_*`-Tools gefahren wird, ist die
Reihenfolge fix:

```text
browser_diag_start(label="<flow_name>")
browser_diag_action(action="navigate", tool="browser_navigate", args={"url": "..."})
browser_diag_action(action="click",    tool="browser_click",    args={"ref":"@e7"}, ref="@e7")
browser_diag_network(only_failures=True)     # Beleg pruefen
browser_diag_console(level="error")          # Beleg pruefen
browser_diag_stop()
browser_diag_report()
```

## Was IMMER erfasst werden muss (Checkliste)

Beim Erstellen eines Flows pruefst du, dass nichts davon fehlt:

- [ ] **Network**: alle Requests/Responses inkl. Bodies (`capture_response_bodies=True`)
- [ ] **Console + Exceptions**: `console=True` — Exceptions duerfen nie unbemerkt sein
- [ ] **Page-Lifecycle**: Navigationen/Dialoge (`page=True`)
- [ ] **Performance**: Metriken (`performance=True`)
- [ ] **Pro Aktion**: Screenshot + DOM + A11y-Snapshot + Element-Details (via `record_action`)
- [ ] **Fehlerpfad**: try/except schreibt den Fehler in die Evidenz (`rec.note(...)`)
- [ ] **Abschluss**: `stop()` + `generate_report()` IM `finally` — sonst geht bei
      Abbruch der Report verloren

## Anti-Patterns (nicht tun)

- KEIN `page.click(...)` / `page.goto(...)` ohne `record_action`-Umklammerung.
  Sonst fehlt der Vorher/Nachher-Beweis und die Aktion ist nicht zuordenbar.
- KEIN nacktes `try: ... except: pass` — verschluckte Fehler sind der Tod der
  Beweiskette. Immer in die Evidenz schreiben und re-raisen.
- KEIN Recorder-Start NACH der ersten Aktion. Fruehe Events (erste Navigation,
  initiale Requests) waeren sonst verloren.
- KEINE selektive Abschaltung von Domains "zur Vereinfachung" ohne Grund. Default
  ist maximal; abschalten nur wenn ein konkretes Volumen-/Datenschutz-Argument
  existiert — und das im Code-Kommentar begruenden.
- KEINE Bewertung des Ergebnisses ohne den generierten Report zu nennen.

## Verifikations-Regel

Ein neu erstellter Flow gilt erst als fertig, wenn ein Test-Lauf eine
`session_<ts>/`-Ordnerstruktur mit nicht-leerer `events.jsonl`, mindestens einem
Action-Record in `actions.json`, Screenshots in `artifacts/` und einer
generierten `report.html` erzeugt hat. "Code kompiliert" ist KEIN Nachweis.

## Querverweise

- Laufzeit-Disziplin: Skill `browser-evidence`
- Tool-Referenz + Session-Layout: `docs/DIAGNOSTICS.md`
- Companion-Doku pro Code-Datei: `docs/code/` (siehe `*.md` neben jeder Quelle)
