from sin_browser_tools.core import manager

async def browser_snapshot() -> dict:
    manager.registry.clear()
    snapshot = await manager.page.accessibility.snapshot(interesting_only=True)
    if not snapshot:
        return {"tree": "(empty page)", "ref_count": 0}
    
    lines = []
    async def walk_node(node, indent=0):
        role = node.get("role", "unknown")
        name = node.get("name", "").strip()
        value = node.get("value", "")
        prefix = "  " * indent
        value_str = f' value="{value}"' if value else ""
        lines.append(f"{prefix}- {role} \"{name}\"{value_str}")
        for child in node.get("children", []):
            await walk_node(child, indent + 1)
    
    await walk_node(snapshot)
    return {"tree": "\n".join(lines), "ref_count": manager.registry.counter}
