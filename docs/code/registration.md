# Companion-Doc: `catalog.py` & `tools/__init__.py` (Registrierung)

> Begleitdokument zu den beiden Dateien, die das Diagnostics-Modul ins
> Tool-System einhaengen. Bei Code-Aenderungen mitpflegen.

## `sin_browser_tools/tools/catalog.py`

Der Catalog ist die Auto-Discovery-Schicht. `TOOL_MODULES` listet die Module,
aus denen `browser_*`-Funktionen als MCP-Tools entdeckt werden.

**Aenderung:** Eintrag `"diagnostics"` zu `TOOL_MODULES` hinzugefuegt und das
Modul im Import-Block ergaenzt. Minimal-invasiv — alle bestehenden Module
(`frames`, `interaction`, `accessibility`, ...) bleiben unveraendert.

Pruefen nach Aenderung:
- `diagnostics` steht in `TOOL_MODULES`.
- `catalog.discover()` enthaelt alle 11 `browser_diag_*`-Tools.

## `sin_browser_tools/tools/__init__.py`

Exportiert die Tool-Module auf Paketebene. **Aenderung:** `diagnostics` zum
Export hinzugefuegt, damit `from sin_browser_tools.tools import diagnostics`
funktioniert und die Auto-Discovery das Modul laden kann.

## Warum minimal

Beide Dateien sind im PR bewusst nur additive Edits (nicht ueberschrieben),
damit der Patch konfliktfrei gegen das Upstream-`main` anwendbar bleibt und keine
anderen Tools versehentlich entfallen.

## Verifikation

`git apply --check` gegen Upstream-`main` muss sauber durchlaufen, danach muessen
`catalog.py`, `__init__.py`, `diagnostics.py`, `evidence.py` kompilieren
(`python -m py_compile`).
