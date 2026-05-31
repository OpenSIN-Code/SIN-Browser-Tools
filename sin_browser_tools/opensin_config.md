# `opensin_config.py`

Lightweight configuration holder with dotted-key access and sensible defaults.

## Defaults
```python
{
  "browser": {"headless": True, "viewport": {"width": 1280, "height": 720}, "timeout": 30000},
  "cdp":     {"auto_scan": True, "ports": [9222, 9223, 9224, 9225]},
}
```

## API

| Symbol | Description |
| --- | --- |
| `OpenSINConfig(config_path?)` | Config object; currently loads the defaults. |
| `.get("a.b.c", default=None)` | Dotted-path lookup; returns `default` if missing. |
| `.export()` | Shallow copy of the config dict. |
| `get_config()` | Returns a module-level singleton `OpenSINConfig`. |

## Usage
```python
from sin_browser_tools.opensin_config import get_config
cfg = get_config()
cfg.get("browser.headless")        # True
cfg.get("cdp.ports")               # [9222, 9223, 9224, 9225]
cfg.get("browser.missing", "x")    # "x"
```

## Notes
- `_load_config()` currently just returns a copy of `DEFAULT_CONFIG`; the
  `config_path` argument is reserved for loading from a file later.
- `.get()` walks the dotted path defensively — a non-dict intermediate value
  yields the `default` instead of raising.
