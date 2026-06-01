"""
Zentrale Konfiguration aus Umgebungsvariablen. Liest SIN_*-Vars und optionale
.env-Datei. Wird von BrowserManager.__init__ konsumiert.
"""

import os
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _as_bool(val: Optional[str], default: bool) -> bool:
    """Parse env-var als boolean."""
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _as_int(val: Optional[str], default: int) -> int:
    """Parse env-var als integer."""
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


class OpenSINConfig:
    """Schreibgeschützte, prozessweite Konfiguration."""

    def __init__(self) -> None:
        # Browser
        self.headless: bool = _as_bool(os.getenv("SIN_HEADLESS"), True)
        self.stealth: bool = _as_bool(os.getenv("SIN_STEALTH"), True)
        self.executable_path: Optional[str] = os.getenv("SIN_BROWSER_EXECUTABLE") or None
        self.viewport_width: int = _as_int(os.getenv("SIN_VIEWPORT_WIDTH"), 1280)
        self.viewport_height: int = _as_int(os.getenv("SIN_VIEWPORT_HEIGHT"), 720)
        self.cdp_url: Optional[str] = os.getenv("SIN_CDP_URL") or None

        # Session & Traces
        self.session_dir: str = os.getenv("SIN_SESSION_DIR", "./.sin_vault")
        self.trace_enabled: bool = _as_bool(os.getenv("SIN_TRACE_ENABLED"), False)
        self.trace_dir: str = os.getenv("SIN_TRACE_DIR", "./.sin_traces")
        self.pii_redaction: bool = _as_bool(os.getenv("SIN_PII_REDACTION"), True)

        # Timeouts
        self.navigation_timeout: int = _as_int(os.getenv("SIN_NAVIGATION_TIMEOUT"), 30000)
        self.action_timeout: int = _as_int(os.getenv("SIN_ACTION_TIMEOUT"), 10000)

        # Logging
        self.log_level: str = os.getenv("SIN_LOG_LEVEL", "INFO").upper()

        # Auto-Record on Failure
        self.auto_record_on_failure: bool = _as_bool(os.getenv("SIN_AUTO_RECORD_ON_FAILURE"), True)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def export(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


_config: Optional[OpenSINConfig] = None


def get_config() -> OpenSINConfig:
    global _config
    if _config is None:
        _config = OpenSINConfig()
    return _config


def reset_config() -> None:
    """Nur für Tests: erzwingt Neu-Einlesen der Env-Vars."""
    global _config
    _config = None
