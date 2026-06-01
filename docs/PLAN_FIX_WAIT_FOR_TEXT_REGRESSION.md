# Plan: Fix `browser_wait_for_text` return-contract regression

Status: RESOLVED (Option B implemented)
Owner: TBD
Introduced by: Issue #22 enhancement (commit `81ff20d`)

> Resolution: Option B applied. `browser_wait_for_text` now returns BOTH the
> legacy `status` key (`found`/`timeout`/`error`) and the Issue #22 `found`
> boolean. Regression test
> `tests/test_tool_smoke.py::test_wait_for_text_returns_both_status_and_found`
> added. Full suite: **103 passed, 2 skipped (macOS-only), 0 failed**.

---

## 1. Symptom

`tests/test_tool_smoke.py::test_navigation_waits` schlägt fehl:

```
found = await navigation.browser_wait_for_text("Smoke Test Page", timeout=5000)
assert found["status"] == "found"
E   KeyError: 'status'
```

Volle Suite: **1 failed, 101 passed, 2 skipped**. Die 2 Skips sind KEINE Fehler
(`tests/test_screen_record.py` ist absichtlich macOS-only).

## 2. Ursache (Root Cause)

Die ursprüngliche `browser_wait_for_text` lieferte ein **status-basiertes** Dict:

```python
# ALT (vor Issue #22)
return {"status": "found", ...}   # bzw. {"status": "timeout", ...}
```

Die im Rahmen von Issue #22 erweiterte Version liefert stattdessen ein
**found-basiertes** Dict:

```python
# NEU (nach Issue #22)
return {"found": True, "text": ..., "element": ..., "method": ...}
return {"found": False, "text": ..., "error": ...}
```

Damit wurde der öffentliche Rückgabe-Vertrag **breaking** geändert. Jeder Agent
oder Test, der `result["status"] == "found"` prüft, bricht. Das ist eine
Regression, kein Testfehler.

## 3. Optionen

| Option | Beschreibung | Bewertung |
|--------|--------------|-----------|
| A | Test an neues Schema anpassen (`result["found"]`) | Verschiebt das Problem auf alle externen Agenten; Breaking Change bleibt |
| B | **Beide Keys zurückgeben** (`status` UND `found`) | Rückwärtskompatibel + neue Felder; minimaler Aufwand |
| C | Auf altes Schema zurück, neue Felder verwerfen | Verliert Shadow-DOM/Element-Info-Mehrwert aus Issue #22 |

**Empfehlung: Option B.** Vertrag additiv halten — alter `status` bleibt
funktionsfähig, neue Felder (`found`, `element`, `matchCount`, `method`) kommen
on top.

## 4. Umsetzung (Option B)

In `sin_browser_tools/tools/navigation.py`, Funktion `browser_wait_for_text`:

```python
if result.get("found"):
    return {
        "status": "found",          # backwards-compatible key
        "found": True,
        "text": text,
        "element": result.get("element"),
        "matchCount": result.get("matchCount", 0),
        "method": result.get("method"),
    }
return {
    "status": "timeout",            # backwards-compatible key
    "found": False,
    "text": text,
    "error": f"Text '{text}' did not appear within {timeout}ms",
    "method": result.get("method"),
}
```

Außerdem: Frame-Resolve-Fehlerpfad ebenfalls um `"status": "error"` ergänzen,
damit alle Rückgaben das `status`-Feld tragen.

## 5. Tests

- `tests/test_tool_smoke.py::test_navigation_waits` muss wieder grün sein
  (prüft `status == "found"`).
- Neuer Test ergänzen: prüft, dass BEIDE Keys existieren
  (`status` und `found`) — Schutz gegen erneute Divergenz.
- Negativfall: nicht vorhandener Text -> `status == "timeout"` und
  `found is False`.

Akzeptanz: `python -m pytest -q` => **0 failed** (2 macOS-Skips bleiben).

## 6. Doku

- `sin_browser_tools/tools/navigation.md`: Rückgabebeispiel um `status` ergänzen.
- `CHANGELOG.md`: Unter Unreleased -> "Fixed: browser_wait_for_text keeps
  backwards-compatible `status` key".

## 7. Nicht-Fehler (zur Klarstellung)

- `tests/test_screen_record.py` (2 Skips): macOS-only, korrektes Verhalten auf
  Linux/CI. Kein Handlungsbedarf.
