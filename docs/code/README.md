# Companion-Docs pro Code-Datei

Zu jeder nicht-trivialen Quelldatei des Diagnostics/Evidence-Layers gibt es hier
ein Begleitdokument mit Zweck, oeffentlicher API, Datenformaten und Fallstricken.

**Regel:** Wer den Code aendert, aktualisiert das zugehoerige Companion-Doc im
selben Commit. Diese Docs sind die Grundlage dafuer, dass Agenten die Tools
korrekt nutzen statt sie ungenutzt liegen zu lassen.

| Quelldatei | Companion-Doc |
|---|---|
| `sin_browser_tools/core/evidence.py` | [`evidence.py.md`](./evidence.py.md) |
| `sin_browser_tools/tools/diagnostics.py` | [`diagnostics.py.md`](./diagnostics.py.md) |
| `sin_browser_tools/tools/catalog.py` + `tools/__init__.py` | [`registration.md`](./registration.md) |

## Weiterfuehrend

- **Nutzer-/Tool-Doku:** [`../DIAGNOSTICS.md`](../DIAGNOSTICS.md)
- **Laufzeit-Disziplin (Agent):** `.opencode/skills/browser-evidence/SKILL.md`
- **Automatisierungen erstellen:** `.opencode/skills/browser-automation/SKILL.md`
