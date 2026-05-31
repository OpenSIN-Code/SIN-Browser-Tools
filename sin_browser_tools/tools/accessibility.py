from sin_browser_tools.core import manager

# Roles that are interactive/clickable and must stay in the snapshot even when
# they have no accessible name (e.g. icon-only buttons common on GMX/web.de).
_INTERACTIVE_ROLES = {
    "button", "link", "textbox", "checkbox", "radio", "switch", "tab",
    "menuitem", "menuitemcheckbox", "menuitemradio", "combobox", "listbox",
    "option", "searchbox", "slider", "spinbutton", "treeitem",
}


async def _build_axtree(pierce: bool) -> dict:
    """Shared CDP accessibility-tree builder.

    Uses ``Accessibility.getFullAXTree`` (with optional ``pierce``) and registers
    every named node by its ``backendDOMNodeId`` so the returned ref-ids
    (@e1, @e2, ...) can be clicked later via ``browser_click`` / ``browser_click_cdp``.

    We use CDP rather than Playwright's ``page.accessibility.snapshot()`` because
    that high-level API was removed in recent Playwright versions and never
    crossed OOPIF / Shadow-DOM boundaries.
    """
    manager.registry.clear()
    lines = []

    cdp = await manager.context.new_cdp_session(manager.page)
    try:
        await cdp.send("Accessibility.enable")
        tree = await cdp.send("Accessibility.getFullAXTree", {"pierce": pierce})
        nodes = tree.get("nodes", [])

        for node in nodes:
            if node.get("ignored"):
                continue

            role = (node.get("role") or {}).get("value", "unknown")
            name = ((node.get("name") or {}).get("value") or "").strip()
            desc = ((node.get("description") or {}).get("value") or "").strip()
            val = (node.get("value") or {}).get("value", "")
            if isinstance(val, str):
                val = val.strip()

            is_interactive = role in _INTERACTIVE_ROLES
            # Skip empty structural containers, but ALWAYS keep interactive
            # controls so icon-only buttons remain clickable.
            if not name and not val and not desc and not is_interactive:
                continue

            ref_str = ""
            backend_node_id = node.get("backendDOMNodeId")
            # Register every node that has a name OR is interactive, so agents
            # can target unlabeled controls too.
            if backend_node_id is not None and (name or val or desc or is_interactive):
                ref_id = manager.registry.register(
                    {
                        "backendDOMNodeId": backend_node_id,
                        "role": role,
                        "name": name,
                    }
                )
                ref_str = f" [{ref_id}]"

            text = " ".join(part for part in (name, desc, str(val)) if part).strip()
            label = text if text else "(unlabeled)"
            lines.append(f'- {role} "{label}"{ref_str}')
    finally:
        try:
            await cdp.detach()
        except Exception:
            pass

    return {
        "tree": "\n".join(lines),
        "ref_count": manager.registry.counter,
        "method": "cdp_pierce" if pierce else "cdp",
    }


async def browser_snapshot() -> dict:
    """Accessibility snapshot of the current page (main document).

    Returns a readable tree plus a ``ref_count`` of registered interactive
    nodes. Every named node gets a ref-id (@e1, @e2, ...) that can be passed to
    ``browser_click`` / ``browser_type``.
    """
    return await _build_axtree(pierce=False)


async def browser_snapshot_full_oopif(pierce: bool = True) -> dict:
    """Bulletproof snapshot for complex pages (OOPIFs, Shadow-DOM, GMX/web.de).

    Uses ``Accessibility.getFullAXTree`` with ``pierce=True`` to read the entire
    accessibility tree across process boundaries (cross-origin iframes) and
    through Shadow-DOM roots. Named nodes are registered by ``backendDOMNodeId``
    so they can be clicked with ``browser_click_cdp`` (or the auto-detecting
    ``browser_click``).
    """
    return await _build_axtree(pierce=pierce)
