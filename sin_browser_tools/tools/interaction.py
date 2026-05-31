from sin_browser_tools.core import manager

async def _resolve_target(target: str):
    if target.startswith("@e"):
        handle = manager.registry.get(target)
        if not handle:
            raise ValueError(f"Ref-ID {target} not found")
        return handle
    return target

async def browser_click(target: str) -> dict:
    resolved = await _resolve_target(target)
    if hasattr(resolved, 'click'):
        await resolved.click(timeout=5000)
    else:
        await manager.page.click(resolved, timeout=5000)
    return {"status": "clicked", "target": target}

async def browser_type(target: str, text: str, clear: bool = True) -> dict:
    resolved = await _resolve_target(target)
    if clear and hasattr(resolved, 'fill'):
        await resolved.fill("")
    if hasattr(resolved, 'type'):
        await resolved.type(text, delay=30)
    else:
        await manager.page.type(resolved, text, delay=30)
    return {"status": "typed", "target": target, "text": text}

async def browser_fill(target: str, value: str) -> dict:
    return await browser_type(target, value, clear=True)

async def browser_upload_file(target: str, file_path: str) -> dict:
    resolved = await _resolve_target(target)
    if hasattr(resolved, 'set_input_files'):
        await resolved.set_input_files(file_path)
    else:
        await manager.page.set_input_files(resolved, file_path)
    return {"status": "uploaded", "file": file_path, "target": target}
