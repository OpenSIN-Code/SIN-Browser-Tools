"""Download tools -- capture files the browser downloads as real artifacts.

The rest of the toolset could *trigger* a download (by clicking a link) but had
no way to **wait for it and persist the file**, so the agent was blind to what
was actually downloaded. These tools close that gap with Playwright's
``expect_download`` and return the saved path + metadata as evidence.
"""

from __future__ import annotations

import os
import time

from sin_browser_tools.core import manager


async def browser_download(
    trigger_ref: str | None = None,
    trigger_selector: str | None = None,
    save_dir: str = "./.sin_downloads",
    timeout_ms: int = 30000,
):
    """Trigger and capture a file download, saving it to ``save_dir``.

    Provide exactly one trigger:
    * ``trigger_ref``      -- an ``@eN`` ref from a snapshot (preferred), or
    * ``trigger_selector`` -- a CSS/text selector for the element to click.

    Returns the saved absolute path, suggested filename, source URL and byte
    size so the download is fully documented, never just assumed.
    """
    page = manager.page
    os.makedirs(save_dir, exist_ok=True)

    async def _click():
        if trigger_ref is not None:
            resolved = manager.registry.get(trigger_ref)
            if resolved is None:
                raise ValueError(
                    f"Ref-ID {trigger_ref} not found. Refs expire on "
                    f"navigation/reload -- call browser_snapshot again."
                )
            # ElementHandle or CDP descriptor both expose .click via page eval;
            # ElementHandle.click() is the common case.
            if hasattr(resolved, "click"):
                await resolved.click()
            else:
                raise ValueError(
                    f"Ref {trigger_ref} is not directly clickable; click it with "
                    f"browser_click first, then call browser_download with a selector."
                )
        elif trigger_selector is not None:
            await page.click(trigger_selector)
        else:
            raise ValueError(
                "Provide trigger_ref or trigger_selector so the download can be started."
            )

    try:
        async with page.expect_download(timeout=timeout_ms) as dl_info:
            await _click()
        download = await dl_info.value
    except Exception as e:  # playwright TimeoutError or click failure
        return {
            "status": "timeout",
            "error": f"No download started within {timeout_ms}ms: {e}",
            "trigger_ref": trigger_ref,
            "trigger_selector": trigger_selector,
        }

    suggested = download.suggested_filename or f"download_{int(time.time())}"
    dest = os.path.abspath(os.path.join(save_dir, suggested))
    await download.save_as(dest)

    size = os.path.getsize(dest) if os.path.exists(dest) else None
    return {
        "status": "downloaded",
        "path": dest,
        "suggested_filename": suggested,
        "url": download.url,
        "size_bytes": size,
    }
