"""SIN-Browser-Tools v2.0 - Enterprise Browser Automation."""

__version__ = "2.0.0"
__author__ = "OpenSIN Team"

from sin_browser_tools.core.manager import BrowserManager
from sin_browser_tools.core.session_vault import SessionVault
from sin_browser_tools.core.frame_traversal import UnifiedFrameTraverser
from sin_browser_tools.core.spa_waker import SPAWaker
from sin_browser_tools.core.pii_redaction import PIIRedactor
from sin_browser_tools.core.observability import TraceLogger
from sin_browser_tools.tools.smart_tools import SmartBrowserTools
from sin_browser_tools.tools.network_intercept import (
    NetworkInterceptor,
    intercept_gmx_emails,
    intercept_api_data,
)

__all__ = [
    "BrowserManager",
    "SessionVault",
    "UnifiedFrameTraverser",
    "SPAWaker",
    "PIIRedactor",
    "TraceLogger",
    "SmartBrowserTools",
    "NetworkInterceptor",
    "intercept_gmx_emails",
    "intercept_api_data",
]
