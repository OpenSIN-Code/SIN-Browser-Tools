"""
Observability Layer -- Tracing, Screenshots und Logs fuer jeden Tool-Call.
Enterprise-Kunden brauchen Debugging-Moeglichkeiten und Audit-Trails.
"""

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from playwright.async_api import Page
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ToolCallTrace:
    """Trace eines einzelnen Tool-Calls."""

    trace_id: str
    tool_name: str
    started_at: float
    duration_ms: float = 0.0
    arguments: dict = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
    network_log_path: Optional[str] = None
    success: bool = True


class TraceLogger:
    """
    Persistiert Traces, Screenshots und Network-Logs pro Tool-Call.
    Ermoeglicht Replay und Debugging von Agent-Fehlern.
    """

    def __init__(self, trace_dir: str = "./.sin_traces", enabled: bool = True):
        self.trace_dir = Path(trace_dir)
        self.enabled = enabled
        self._current_traces: list[ToolCallTrace] = []
        self._network_buffer: list[dict] = []

        if self.enabled:
            self.trace_dir.mkdir(parents=True, exist_ok=True)

    async def trace_tool_call(
        self,
        tool_name: str,
        arguments: dict,
        func: Callable,
        page: Optional[Page] = None,
        capture_screenshot: bool = True,
    ) -> Any:
        """
        Wrapper: Fuehrt Tool-Call aus und tracet alles.

        Usage::

            result = await tracer.trace_tool_call("browser_click", {...}, actual_func, page)
        """
        if not self.enabled:
            return await func()

        trace_id = str(uuid.uuid4())[:8]
        trace = ToolCallTrace(
            trace_id=trace_id,
            tool_name=tool_name,
            started_at=time.time(),
            arguments=arguments,
        )

        self._network_buffer = []

        listener_attached = False
        try:
            if page:
                page.on("response", self._capture_network)
                listener_attached = True

            result = await func()
            trace.result = self._safe_serialize(result)
            trace.success = True

        except Exception as e:
            trace.error = str(e)
            trace.success = False
            logger.error("Tool call failed", tool=tool_name, error=str(e))
            raise

        finally:
            # BUGFIX: Listener IMMER wieder entfernen. Frueher wurde der
            # "response"-Listener bei jedem Tool-Call neu registriert und nie
            # geloest -> Listener-Leak (jeder Call sammelte zusaetzlich die
            # Responses aller vorherigen Calls + stetig wachsender Speicher).
            if listener_attached and page:
                try:
                    page.remove_listener("response", self._capture_network)
                except Exception:
                    pass

            trace.duration_ms = (time.time() - trace.started_at) * 1000

            if page and capture_screenshot:
                try:
                    screenshot_path = self.trace_dir / f"{trace_id}_{tool_name}.png"
                    await page.screenshot(path=str(screenshot_path), full_page=False)
                    trace.screenshot_path = str(screenshot_path)
                except Exception as e:
                    logger.debug("Screenshot failed", error=str(e))

            if self._network_buffer:
                net_path = self.trace_dir / f"{trace_id}_network.json"
                with open(net_path, "w", encoding="utf-8") as f:
                    json.dump(self._network_buffer, f, indent=2)
                trace.network_log_path = str(net_path)

            self._current_traces.append(trace)
            self._persist_trace(trace)

        return result

    def _capture_network(self, response: Any):
        """Sammelt Network-Events fuer Debugging."""
        try:
            self._network_buffer.append(
                {
                    "url": response.url,
                    "status": response.status,
                    "method": response.request.method,
                    "timestamp": time.time(),
                    "content_type": response.headers.get("content-type", ""),
                }
            )
        except Exception:
            pass

    @staticmethod
    def _safe_serialize(obj: Any) -> Any:
        """Serialisiert Objekte sicher fuer JSON."""
        try:
            if hasattr(obj, "__dict__"):
                return str(obj)
            json.dumps(obj)
            return obj
        except Exception:
            return str(obj)

    def _persist_trace(self, trace: ToolCallTrace):
        """Speichert Trace als JSON."""
        try:
            trace_file = self.trace_dir / f"{trace.trace_id}_trace.json"
            with open(trace_file, "w", encoding="utf-8") as f:
                json.dump(asdict(trace), f, indent=2, default=str)
        except Exception as e:
            logger.warning("Trace persist failed", error=str(e))

    async def save_session_trace(self, name: str = "session"):
        """Speichert die gesamte Session als zusammenhaengenden Trace."""
        if not self.enabled or not self._current_traces:
            return

        session_trace = {
            "session_id": str(uuid.uuid4())[:8],
            "name": name,
            "started_at": self._current_traces[0].started_at,
            "ended_at": time.time(),
            "tool_calls": [asdict(t) for t in self._current_traces],
            "summary": {
                "total_calls": len(self._current_traces),
                "failed_calls": sum(1 for t in self._current_traces if not t.success),
                "total_duration_ms": sum(t.duration_ms for t in self._current_traces),
            },
        }

        session_file = self.trace_dir / f"session_{name}_{int(time.time())}.json"
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session_trace, f, indent=2, default=str)

        logger.info(
            "Session trace saved",
            file=str(session_file),
            calls=len(self._current_traces),
        )

    def clear(self):
        """Loescht aktuelle Traces (nicht die Dateien auf Disk)."""
        self._current_traces = []

    def get_traces(self) -> list[ToolCallTrace]:
        return list(self._current_traces)
