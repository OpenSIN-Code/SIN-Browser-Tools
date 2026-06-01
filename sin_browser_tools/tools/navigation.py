from sin_browser_tools.core import manager


def _invalidate_refs() -> None:
    """Drop all @eN refs. They point at the PREVIOUS document and become stale
    the moment we navigate -- clicking one afterwards would target a detached or
    wrong node. Callers must browser_snapshot again to get fresh refs.
    """
    manager.registry.clear()


async def browser_navigate(url: str) -> dict:
    response = await manager.page.goto(url, wait_until="domcontentloaded", timeout=30000)
    _invalidate_refs()
    return {"status": response.status if response else "unknown", "url": manager.page.url}


async def browser_back() -> dict:
    await manager.page.go_back(wait_until="domcontentloaded")
    _invalidate_refs()
    return {"status": "navigated_back", "url": manager.page.url}


async def browser_forward() -> dict:
    await manager.page.go_forward(wait_until="domcontentloaded")
    _invalidate_refs()
    return {"status": "navigated_forward", "url": manager.page.url}


async def browser_reload() -> dict:
    await manager.page.reload(wait_until="domcontentloaded")
    _invalidate_refs()
    return {"status": "reloaded", "url": manager.page.url}


async def browser_scroll(direction: str = "down", amount: int = 500) -> dict:
    delta = amount if direction == "down" else -amount
    await manager.page.evaluate(f"window.scrollBy(0, {delta})")
    return {"status": "scrolled", "direction": direction, "amount": amount}


async def browser_press(key: str) -> dict:
    """Press a key or key combination, e.g. 'Enter', 'Control+A', 'Escape'."""
    await manager.page.keyboard.press(key)
    return {"status": "pressed", "key": key}


async def browser_get_url() -> dict:
    return {"url": manager.page.url, "title": await manager.page.title()}


async def browser_set_viewport(width: int = 1280, height: int = 720) -> dict:
    """Resize the viewport, e.g. to test responsive layouts or mobile widths."""
    await manager.page.set_viewport_size({"width": width, "height": height})
    return {"status": "resized", "width": width, "height": height}


async def browser_wait_for(selector: str, state: str = "visible", timeout: float = 10000) -> dict:
    """Wait for a selector to reach a state ('attached', 'detached', 'visible', 'hidden')."""
    try:
        await manager.page.wait_for_selector(selector, state=state, timeout=timeout)
        return {"status": "ready", "selector": selector, "state": state}
    except Exception as e:
        return {"status": "timeout", "selector": selector, "error": str(e)}


async def browser_wait_for_text(text: str, timeout: float = 10000) -> dict:
    """Wait until the given text appears anywhere on the page."""
    try:
        await manager.page.wait_for_function(
            "t => document.body && document.body.innerText.includes(t)",
            arg=text,
            timeout=timeout,
        )
        return {"status": "found", "text": text}
    except Exception as e:
        return {"status": "timeout", "text": text, "error": str(e)}


async def browser_wait_for_load(state: str = "networkidle", timeout: float = 15000) -> dict:
    """Wait for a page load state ('load', 'domcontentloaded', 'networkidle')."""
    try:
        await manager.page.wait_for_load_state(state, timeout=timeout)
        return {"status": "loaded", "state": state, "url": manager.page.url}
    except Exception as e:
        return {"status": "timeout", "state": state, "error": str(e)}


# ---------------------------------------------------------------------------
# browser_wait_for_spa_transition -- MutationObserver-based DOM-text waiter
# (Issue #23).
#
# Why a dedicated tool (vs. browser_wait_for_text):
#   React/Vue/Angular SPAs change the rendered step WITHOUT changing the URL or
#   firing a navigation/load event -- e.g. a multi-step onboarding form where
#   clicking "Continue" swaps step 1 for step 2 in place. wait_for_load /
#   networkidle never fire, so the only reliable signal is "did this text appear
#   in the DOM yet?". This tool installs a MutationObserver inside the page (or a
#   named/URL-matched frame), so it resolves the instant the target text is
#   inserted -- including text rendered into OPEN shadow roots -- instead of
#   polling on a fixed interval.
#
# Ported and hardened from SINator-FireworksAI agent_toolbox/core/browser_utils
# (wait_for_spa_transition), which used the same MutationObserver approach for
# the Fireworks onboarding 2-step SPA.
# ---------------------------------------------------------------------------

_SPA_TRANSITION_JS = r"""
(args) => {
  const { targetText, timeoutMs, pierceShadow } = args;
  const needle = targetText;

  // Read visible text across the document AND any OPEN shadow roots, because
  // web-component SPAs render step content inside shadow DOM where
  // document.body.innerText cannot see it.
  const collectText = () => {
    let text = (document.body && document.body.innerText) || '';
    if (pierceShadow && document.body) {
      const stack = [document.body];
      while (stack.length) {
        const node = stack.pop();
        let kids;
        try { kids = node.querySelectorAll('*'); } catch (e) { continue; }
        kids.forEach((el) => {
          if (el.shadowRoot && el.shadowRoot.mode === 'open') {
            text += ' ' + (el.shadowRoot.textContent || '');
            stack.push(el.shadowRoot);
          }
        });
      }
    }
    return text;
  };

  const hit = () => collectText().includes(needle);

  return new Promise((resolve) => {
    if (hit()) { resolve({ found: true, method: 'immediate' }); return; }

    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      try { observer.disconnect(); } catch (e) {}
      clearTimeout(timer);
      resolve(result);
    };

    const observer = new MutationObserver(() => {
      if (hit()) finish({ found: true, method: 'observer' });
    });
    try {
      observer.observe(document.documentElement || document.body, {
        childList: true,
        subtree: true,
        characterData: true,
      });
    } catch (e) {
      finish({ found: hit(), method: 'observe_failed' });
      return;
    }

    const timer = setTimeout(() => {
      finish({ found: hit(), method: hit() ? 'timeout_check' : 'timeout' });
    }, timeoutMs);
  });
}
"""


async def browser_wait_for_spa_transition(
    target_text: str,
    timeout_ms: int = 30000,
    pierce_shadow: bool = True,
    frame_name: str = None,
    frame_url: str = None,
) -> dict:
    """Wait for an SPA DOM transition by watching for ``target_text`` to appear
    via a MutationObserver (Issue #23).

    Use this when a React/Vue/Angular app swaps content WITHOUT a navigation or
    URL change -- e.g. a multi-step onboarding form where "Continue" replaces
    step 1 with step 2 in place. ``browser_wait_for_load`` / networkidle never
    fire for those; this tool resolves the instant ``target_text`` is inserted
    into the DOM (open shadow roots included), so you can call it right after a
    click instead of sleeping a fixed amount.

    Args:
        target_text: substring to wait for in the rendered text.
        timeout_ms: max time to wait before giving up (default 30s).
        pierce_shadow: also scan text inside OPEN shadow roots (default True;
            needed for web-component SPAs).
        frame_name / frame_url: watch inside a named/URL-matched iframe instead
            of the main frame (same semantics as the ``browser_*_in_frame``
            tools).

    Returns:
        ``{"status": "found", "method": ..., "target_text": ...}`` once the text
        appears, or ``{"status": "timeout", "target_text": ..., ...}`` if it
        never did within ``timeout_ms``. ``method`` is one of ``immediate`` /
        ``observer`` / ``timeout_check`` and is handy for debugging flaky steps.
    """
    # Lazy import to avoid a circular import at module load
    # (frames -> manager, navigation -> manager).
    from sin_browser_tools.tools.frames import _resolve_frame

    frame, error = _resolve_frame(frame_name, frame_url)
    if error:
        return {"status": "error", "target_text": target_text, "error": error}

    args = {
        "targetText": target_text,
        "timeoutMs": max(0, int(timeout_ms)),
        "pierceShadow": bool(pierce_shadow),
    }
    try:
        result = await frame.evaluate(_SPA_TRANSITION_JS, args)
    except Exception as e:
        return {"status": "timeout", "target_text": target_text, "error": str(e)}

    if result.get("found"):
        return {
            "status": "found",
            "method": result.get("method"),
            "target_text": target_text,
        }
    return {
        "status": "timeout",
        "method": result.get("method"),
        "target_text": target_text,
        "error": (
            f"Text {target_text!r} did not appear within {timeout_ms}ms. The SPA "
            "step may not have advanced, the text may differ, or it may live in "
            "a closed shadow root."
        ),
    }


# --- Tab / window management -------------------------------------------------

async def browser_list_tabs() -> dict:
    """List all open tabs in the current context with their index, url and title."""
    pages = manager.context.pages
    tabs = []
    for i, p in enumerate(pages):
        try:
            title = await p.title()
        except Exception:
            title = ""
        tabs.append({
            "index": i,
            "url": p.url,
            "title": title,
            "active": p is manager.page,
        })
    return {"count": len(tabs), "tabs": tabs}


async def browser_new_tab(url: str = None) -> dict:
    """Open a new tab and make it the active page. Optionally navigate to a URL."""
    page = await manager.context.new_page()
    manager.set_active_page(page)
    if url:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    return {"status": "opened", "index": manager.context.pages.index(page), "url": page.url}


async def browser_switch_tab(index: int) -> dict:
    """Switch the active page to the tab at the given index."""
    pages = manager.context.pages
    if index < 0 or index >= len(pages):
        raise ValueError(f"Tab index {index} out of range (0..{len(pages) - 1})")
    page = pages[index]
    manager.set_active_page(page)
    await page.bring_to_front()
    return {"status": "switched", "index": index, "url": page.url}


async def browser_close_tab(index: int = None) -> dict:
    """Close a tab by index (defaults to the active tab) and re-focus another."""
    pages = manager.context.pages
    if index is not None and (index < 0 or index >= len(pages)):
        raise ValueError(f"Tab index {index} out of range (0..{len(pages) - 1})")
    page = manager.page if index is None else pages[index]
    was_active = page is manager.page
    await page.close()
    remaining = manager.context.pages
    # Only move focus if we actually closed the active tab; closing a background
    # tab must leave the user's current tab focused.
    if was_active and remaining:
        manager.set_active_page(remaining[-1])
    elif not remaining:
        # BUGFIX: frueher 'manager.page = None'. `page` ist eine read-only
        # Property (sowohl auf dem Proxy als auch auf BrowserManager) -> das warf
        # AttributeError und liess den Tab-Close im Fehlerfall haengen. Wir
        # nutzen jetzt den dafuer vorgesehenen Helper.
        manager.clear_active_page()
    # `manager.page` wirft, wenn keine Page mehr aktiv ist -> intern abfragen.
    active_page = manager.active_page
    return {
        "status": "closed",
        "remaining": len(remaining),
        "active_url": active_page.url if active_page else None,
    }
