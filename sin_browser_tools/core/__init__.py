"""SIN-Browser-Tools core package."""

from sin_browser_tools.core.manager import BrowserManager, manager
from sin_browser_tools.core.frame_traversal import UnifiedFrameTraverser
from sin_browser_tools.core.spa_waker import SPAWaker
from sin_browser_tools.core.session_vault import SessionVault
from sin_browser_tools.core.pii_redaction import PIIRedactor
from sin_browser_tools.core.observability import TraceLogger

__all__ = [
    "BrowserManager",
    "manager",          # v1.x-kompatibler Singleton-Proxy
    "UnifiedFrameTraverser",
    "SPAWaker",
    "SessionVault",
    "PIIRedactor",
    "TraceLogger",
]
