"""Canonical tool-result contract for SIN-Browser-Tools.

Why this exists
---------------
Every ``browser_*`` tool returns a rich, *semantic* status string
(``"clicked"``, ``"found"``, ``"timeout"``, ``"not_found"`` ...). That detail is
valuable, but an agent needs **one reliable boolean** to branch on -- it should
never have to memorise which of 40+ status strings count as success.

``normalize_result`` runs at the single MCP dispatch chokepoint and injects a
canonical, machine-checkable envelope **without throwing away** the semantic
status:

    {"ok": true,  "status": "clicked", "ref": "@e7", ...}
    {"ok": false, "status": "timeout", "selector": "#go", ...}
    {"ok": false, "error": "Ref-ID @e9 not found", "tool": "browser_click"}

Design rules
------------
* Backwards compatible: the original keys (``status``, ``error``, payload) stay
  exactly as the tool produced them. We only *add* ``ok`` when it is missing.
* Honest: ``ok`` is derived from explicit, documented failure semantics -- not
  guessed. If a tool already set ``ok``, we never override it.
* Total: a non-dict return is wrapped so the contract holds for every tool.
"""

from __future__ import annotations

from typing import Any

# Status strings that mean "the requested action did NOT achieve its goal".
# Kept explicit and conservative so the boolean is trustworthy. Everything not
# listed here (clicked, typed, found, navigated, started, ...) is a success.
FAILURE_STATUSES = frozenset(
    {
        "error",
        "timeout",
        "not_found",
        "missing_file",
        "failed",
        "unavailable",
        "blocked",
    }
)


def is_failure(result: dict) -> bool:
    """Return True if a result dict represents a failed/no-goal outcome.

    The order of checks is the contract:
    1. An explicit ``ok`` field always wins (tool already decided).
    2. A non-empty ``error`` field means failure.
    3. A ``status`` in :data:`FAILURE_STATUSES` means failure.
    Otherwise it is a success.
    """
    if "ok" in result:
        return not bool(result["ok"])
    if result.get("error") not in (None, "", False):
        return True
    if result.get("status") in FAILURE_STATUSES:
        return True
    return False


def normalize_result(result: Any) -> Any:
    """Inject a canonical ``ok`` boolean into a tool result.

    * dict  -> same dict with ``ok`` added (existing ``ok`` is preserved).
    * other -> wrapped as ``{"ok": True, "result": <value>}`` so even tools that
      return a bare string/list/None satisfy the contract.

    The function never mutates the input dict; it returns a shallow copy.
    """
    if isinstance(result, dict):
        if "ok" in result:
            return result
        out = dict(result)
        out["ok"] = not is_failure(out)
        return out
    return {"ok": True, "result": result}


def ok(**fields: Any) -> dict:
    """Helper for tool authors: build a success envelope.

    Example::

        return ok(status="clicked", ref=ref, x=x, y=y)
    """
    payload = {"ok": True}
    payload.update(fields)
    return payload


def err(error: str, **fields: Any) -> dict:
    """Helper for tool authors: build a failure envelope.

    Example::

        return err("element not visible", status="error", ref=ref)
    """
    payload = {"ok": False, "error": error}
    payload.update(fields)
    return payload
