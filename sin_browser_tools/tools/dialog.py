from sin_browser_tools.core import manager


async def browser_dialog(action: str, prompt_text: str = None) -> dict:
    """Accept or dismiss the pending native JS dialog (alert/confirm/prompt).

    Works both standalone and after ``browser_wait_for_dialog`` -- the dialog is
    only consumed (and the page un-blocked) once it is actually accepted or
    dismissed here, so the wait->act recipe no longer drops the dialog.
    """
    if action not in ("accept", "dismiss"):
        return {
            "status": "error",
            "error": f"Invalid action '{action}'. Use 'accept' or 'dismiss'.",
        }

    # consume=True: take ownership of the dialog so we can act on it exactly once.
    dialog_info = await manager.get_next_dialog(timeout=3.0, consume=True)
    if not dialog_info:
        return {"status": "no_dialog_pending"}

    dialog = dialog_info["dialog"]
    if action == "accept":
        await dialog.accept(prompt_text or dialog_info["default_value"] or "")
    else:
        await dialog.dismiss()

    return {"status": action + "ed", "dialog_type": dialog_info["type"], "message": dialog_info["message"]}


async def browser_wait_for_dialog(timeout: float = 10.0) -> dict:
    """Wait for a native dialog to appear WITHOUT consuming it.

    The detected dialog stays pending so the very next ``browser_dialog("accept")``
    / ``browser_dialog("dismiss")`` acts on the same live dialog. (Previously this
    consumed the dialog, leaving a follow-up accept with nothing to act on and the
    page blocked behind an un-handled native dialog.)
    """
    # consume=False: peek only, leave the dialog pending for browser_dialog().
    dialog_info = await manager.get_next_dialog(timeout=timeout, consume=False)
    if not dialog_info:
        return {"status": "timeout"}
    return {"status": "dialog_detected", "type": dialog_info["type"], "message": dialog_info["message"]}
