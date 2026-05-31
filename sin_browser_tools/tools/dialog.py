from sin_browser_tools.core import manager

async def browser_dialog(action: str, prompt_text: str = None) -> dict:
    dialog_info = await manager.get_next_dialog(timeout=3.0)
    if not dialog_info:
        return {"status": "no_dialog_pending"}
    
    dialog = dialog_info["dialog"]
    if action == "accept":
        await dialog.accept(prompt_text or dialog_info["default_value"] or "")
    elif action == "dismiss":
        await dialog.dismiss()
    
    return {"status": action + "ed", "dialog_type": dialog_info["type"], "message": dialog_info["message"]}

async def browser_wait_for_dialog(timeout: float = 10.0) -> dict:
    dialog_info = await manager.get_next_dialog(timeout=timeout)
    if not dialog_info:
        return {"status": "timeout"}
    return {"status": "dialog_detected", "type": dialog_info["type"], "message": dialog_info["message"]}
