# `tools/__init__.py`

Package initializer for the tool modules. It eagerly imports every tool module
and re-exports them via `__all__`:

```python
from . import accessibility, interaction, navigation, vision, dialog, extraction
__all__ = ["accessibility", "interaction", "navigation", "vision", "dialog", "extraction"]
```

## Purpose
- Lets consumers do `from sin_browser_tools.tools import navigation` and lets
  `catalog.discover()` import the modules it scans.
- Keeps the package's public tool surface explicit.

## Note
`catalog` itself is intentionally **not** re-exported here; it imports the tool
modules (including `accessibility` and `interaction`), so importing it from the
package `__init__` would create a circular import. Import `catalog` directly
(`from sin_browser_tools.tools import catalog`) instead.
