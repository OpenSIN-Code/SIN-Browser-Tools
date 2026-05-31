import json
from pathlib import Path
from typing import Optional, Dict, Any

class OpenSINConfig:
    DEFAULT_CONFIG = {
        "browser": {"headless": True, "viewport": {"width": 1280, "height": 720}, "timeout": 30000},
        "cdp": {"auto_scan": True, "ports": [9222, 9223, 9224, 9225]},
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        return self.DEFAULT_CONFIG.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def export(self) -> Dict[str, Any]:
        return self.config.copy()

_config = None
def get_config() -> OpenSINConfig:
    global _config
    if _config is None:
        _config = OpenSINConfig()
    return _config
